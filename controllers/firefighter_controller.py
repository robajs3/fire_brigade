from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps

from services.firefighter_service import FirefighterService
from services.user_service import UserService
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
    nfc_username = request.form.get("nfc_username")
    nfc_hash     = request.form.get("nfc_hash")
    role         = request.form.get("role", "strazak")

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

    # Wyposażenie obowiązkowe
    required_items = RoleRequiredItem.query.filter_by(
        role=firefighter.role,
        is_required=True
    ).all()

    # Mapa catalog_id -> item_id dla wydanych przedmiotów
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

    # Przedmioty spoza wyposażenia obowiązkowego
    extra_items = [
        item for item in issued_items
        if item.catalog_id not in required_catalog_ids
    ]

    return render_template(
        "firefighters/detail.html",
        firefighter=firefighter,
        issued_items=issued_items,
        equipment_status=equipment_status,
        extra_items=extra_items,
    )


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
    nfc_username = request.form.get("nfc_username")
    nfc_hash     = request.form.get("nfc_hash")
    role         = request.form.get("role", "strazak")

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
    from flask import jsonify
    firefighter = FirefighterService.get_by_nfc_hash(nfc_hash)
    if not firefighter:
        return jsonify({"error": "Nie znaleziono"}), 404
    return jsonify({
        "id":        firefighter.firefighter_id,
        "full_name": firefighter.full_name
    })