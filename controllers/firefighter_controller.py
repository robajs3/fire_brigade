from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
from datetime import date as dt
from models.user_model import db
from services.firefighter_service import FirefighterService
from services.user_service import UserService
from services.catalog_service import CatalogService
from services.item_service import ItemService
from models.firefighter_model import Firefighter
from models.item_model import RoleRequiredItem, Item

firefighter_bp = Blueprint("firefighter_controller", __name__, url_prefix="/Sp")


def role_required(required_roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cas_username = session.get("CAS_USERNAME")
            if not cas_username:
                return redirect(url_for("user_controller.unauthorize"))
            user = UserService.get_user_by_cas_username(cas_username)
            if not user or not user.is_active:
                return redirect(url_for("user_controller.unauthorize"))
            if required_roles and user.role not in required_roles:
                return redirect(url_for("user_controller.unauthorize"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@firefighter_bp.route("/firefighters")
@role_required()
def firefighters_list():
    firefighters = FirefighterService.get_all_active()
    return render_template("firefighters/list.html", firefighters=firefighters)


@firefighter_bp.route("/firefighters/add", methods=["GET"])
@role_required(["manager", "admin"])
def add_firefighter_form():
    return render_template("firefighters/add.html")


@firefighter_bp.route("/firefighters/add", methods=["POST"])
@role_required(["manager", "admin"])
def add_firefighter_post():
    first_name   = request.form.get("first_name")
    last_name    = request.form.get("last_name")
    nfc_username = request.form.get("nfc_username") or None
    nfc_hash     = request.form.get("nfc_hash") or None
    role         = request.form.get("role", "strazak")

    if nfc_hash:
        existing = FirefighterService.get_by_nfc_hash(nfc_hash)
        if existing:
            flash(f"Ta karta NFC jest już przypisana do: {existing.full_name}.", "danger")
            return redirect(url_for("firefighter_controller.add_firefighter_form"))

    firefighter = FirefighterService.create(
        first_name=first_name,
        last_name=last_name,
        nfc_username=nfc_username,
        nfc_hash=nfc_hash,
        role=role
    )

    if firefighter:
        flash("Dodano strażaka.", "success")
    else:
        flash("Błąd podczas dodawania.", "danger")

    return redirect(url_for("firefighter_controller.firefighters_list"))


@firefighter_bp.route("/firefighters/<int:id>")
@role_required()
def firefighter_detail(id):
    firefighter = FirefighterService.get_by_id(id)
    if not firefighter:
        flash("Nie znaleziono strażaka.", "danger")
        return redirect(url_for("firefighter_controller.firefighters_list"))

    issued_items = FirefighterService.get_issued_items(id)

    required_items = RoleRequiredItem.query.filter_by(
        role=firefighter.role,
        is_required=True
    ).all()

    issued_by_catalog = {}
    for item in issued_items:
        if item.catalog_id and item.catalog_id not in issued_by_catalog:
            issued_by_catalog[item.catalog_id] = item.item_id

    equipment_status = []
    required_catalog_ids = set()
    for req in required_items:
        required_catalog_ids.add(req.catalog_id)
        equipment_status.append({
            "name":       req.catalog_item.name,
            "quantity":   req.quantity,
            "catalog_id": req.catalog_id,
            "has_it":     req.catalog_id in issued_by_catalog,
            "item_id":    issued_by_catalog.get(req.catalog_id),
        })

    extra_items = [
        item for item in issued_items
        if item.catalog_id not in required_catalog_ids
    ]
    catalog = CatalogService.get_all_active()
    from models.item_model import IssuanceLog
    from models.user_model import User

    logs = (
        db.session.query(IssuanceLog, Item, User)
        .join(Item, IssuanceLog.item_id == Item.item_id)
        .outerjoin(User, IssuanceLog.performed_by == User.user_id)
        .filter(IssuanceLog.firefighter_id == id)
        .order_by(IssuanceLog.performed_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "firefighters/detail.html",
        firefighter=firefighter,
        issued_items=issued_items,
        equipment_status=equipment_status,
        extra_items=extra_items,
        catalog=catalog,
        logs=logs,
        today=dt.today().isoformat()
    )


@firefighter_bp.route("/firefighters/<int:id>/issue", methods=["POST"])
@role_required(["manager", "admin"])
def issue_from_detail(id):
    firefighter = FirefighterService.get_by_id(id)
    if not firefighter:
        flash("Nie znaleziono strażaka.", "danger")
        return redirect(url_for("firefighter_controller.firefighters_list"))

    catalog_id = request.form.get("catalog_id")
    issue_date = request.form.get("issue_date") or dt.today().isoformat()
    clothing   = request.form.get("clothing_card_number") or None
    notes      = request.form.get("notes") or None

    if not catalog_id:
        flash("Wybierz przedmiot.", "danger")
        return redirect(url_for("firefighter_controller.firefighter_detail", id=id))

    catalog_entry = CatalogService.get_by_id(int(catalog_id))
    if not catalog_entry:
        flash("Nie znaleziono przedmiotu w katalogu.", "danger")
        return redirect(url_for("firefighter_controller.firefighter_detail", id=id))

    user = UserService.get_user_by_cas_username(session["CAS_USERNAME"])

    # Pobierz istniejący przedmiot z magazynu zamiast tworzyć nowy
    item = Item.query.filter_by(
        catalog_id=int(catalog_id),
        is_consumed=False,
        firefighter_id=None
    ).first()

    if not item:
        flash(f"Brak '{catalog_entry.name}' w magazynie.", "danger")
        return redirect(url_for("firefighter_controller.firefighter_detail", id=id))

    item = ItemService.issue_item(
        item_id=item.item_id,
        firefighter_id=id,
        issue_date=issue_date,
        performed_by_user_id=user.user_id,
        clothing_card_number=clothing,
        notes=notes,
        nfc_scan=False
    )

    if item:
        flash(f"Wydano: {catalog_entry.name} dla {firefighter.full_name}.", "success")
    else:
        flash("Błąd podczas wydania.", "danger")

    return redirect(url_for("firefighter_controller.firefighter_detail", id=id))

@firefighter_bp.route("/firefighters/<int:id>/edit", methods=["GET"])
@role_required(["manager", "admin"])
def edit_firefighter_form(id):
    firefighter = FirefighterService.get_by_id(id)
    if not firefighter:
        flash("Nie znaleziono strażaka.", "danger")
        return redirect(url_for("firefighter_controller.firefighters_list"))
    return render_template("firefighters/edit.html", firefighter=firefighter)


@firefighter_bp.route("/firefighters/<int:id>/edit", methods=["POST"])
@role_required(["manager", "admin"])
def edit_firefighter_post(id):
    first_name   = request.form.get("first_name")
    last_name    = request.form.get("last_name")
    nfc_username = request.form.get("nfc_username") or None
    nfc_hash     = request.form.get("nfc_hash") or None
    role         = request.form.get("role", "strazak")

    if nfc_hash:
        existing = FirefighterService.get_by_nfc_hash(nfc_hash)
        if existing and existing.firefighter_id != id:
            flash(f"Ta karta NFC jest już przypisana do: {existing.full_name}.", "danger")
            return redirect(url_for("firefighter_controller.edit_firefighter_form", id=id))

    updated = FirefighterService.update(
        id,
        first_name=first_name,
        last_name=last_name,
        nfc_username=nfc_username,
        nfc_hash=nfc_hash,
        role=role
    )

    if updated:
        flash("Zapisano zmiany.", "success")
    else:
        flash("Błąd podczas zapisu.", "danger")

    return redirect(url_for("firefighter_controller.firefighter_detail", id=id))


@firefighter_bp.route("/firefighters/<int:id>/deactivate", methods=["POST"])
@role_required(["admin"])
def deactivate_firefighter(id):
    result = FirefighterService.deactivate(id)
    if result:
        flash("Strażak został dezaktywowany.", "success")
    else:
        flash("Nie udało się dezaktywować strażaka.", "danger")
    return redirect(url_for("firefighter_controller.firefighters_list"))


@firefighter_bp.route("/firefighters/<int:id>/delete", methods=["POST"])
@role_required(["admin"])
def delete_firefighter(id):
    result = FirefighterService.delete(id)
    if result:
        flash("Strażak został usunięty.", "success")
    else:
        flash("Nie można usunąć – strażak ma wydane przedmioty.", "danger")
    return redirect(url_for("firefighter_controller.firefighters_list"))


@firefighter_bp.route("/api/firefighters/by-nfc/<nfc_hash>")
@role_required()
def api_firefighter_by_nfc(nfc_hash):
    firefighter = FirefighterService.get_by_nfc_hash(nfc_hash)
    if not firefighter:
        return jsonify({"error": "Nie znaleziono"}), 404
    return jsonify({
        "id":        firefighter.firefighter_id,
        "full_name": firefighter.full_name
    })