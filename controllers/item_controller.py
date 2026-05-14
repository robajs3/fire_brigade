print(">>> ŁADUJE items_list z pliku:", __file__)

from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from functools import wraps

from services.user_service import UserService
from services.item_service import ItemService
from services.firefighter_service import FirefighterService
from models.user_model import db
from models.item_model import Item, IssuanceLog
from models.firefighter_model import Firefighter

item_bp = Blueprint("item_controller", __name__, url_prefix="/Sp")


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


@item_bp.route("/items")
@role_required()
def items_list():
    status  = request.args.get("status", "all")
    grouped = ItemService.get_grouped_by_catalog()

    if status == "stock":
        grouped = [g for g in grouped if g["in_stock"] > 0]
    elif status == "issued":
        grouped = [g for g in grouped if g["issued"] > 0]

    userCAS = session.get("CAS_USERNAME")
    return render_template("items/list.html", grouped=grouped, status=status, userCAS=userCAS)


@item_bp.route("/items/stock")
@role_required()
def items_stock():
    items = ItemService.get_all_in_stock()
    userCAS = session.get("CAS_USERNAME")
    return render_template("items/stock.html", items=items, userCAS=userCAS)


@item_bp.route("/items/consumed")
@role_required()
def items_consumed():
    from sqlalchemy import desc
    items = Item.query.filter_by(is_consumed=True).order_by(Item.updated_at.desc()).all()
    userCAS = session.get("CAS_USERNAME")

    consumed_data = []
    for item in items:
        log = (
            db.session.query(IssuanceLog, Firefighter)
            .outerjoin(Firefighter, IssuanceLog.firefighter_id == Firefighter.firefighter_id)
            .filter(IssuanceLog.item_id == item.item_id)
            .filter(IssuanceLog.action == "consumed")
            .order_by(IssuanceLog.performed_at.desc())
            .first()
        )
        issued_log = (
            db.session.query(IssuanceLog, Firefighter)
            .outerjoin(Firefighter, IssuanceLog.firefighter_id == Firefighter.firefighter_id)
            .filter(IssuanceLog.item_id == item.item_id)
            .filter(IssuanceLog.action == "issued")
            .order_by(IssuanceLog.performed_at.desc())
            .first()
        )
        consumed_data.append({
            "item":        item,
            "consumed_at": log[0].performed_at if log else None,
            "firefighter": issued_log[1] if issued_log else None,
            "issue_date":  issued_log[0].performed_at.date() if issued_log else None,
        })

    return render_template("items/consumed.html", consumed_data=consumed_data, userCAS=userCAS)


@item_bp.route("/items/add", methods=["GET"])
@role_required()
def add_item_form():
    from services.catalog_service import CatalogService
    catalog = CatalogService.get_all_active()
    return render_template("items/add.html", catalog=catalog)


@item_bp.route("/items/add", methods=["POST"])
@role_required(["manager", "admin"])
def add_item_post():
    from services.catalog_service import CatalogService

    catalog_id = request.form.get("catalog_id")
    count      = request.form.get("count", 1)
    clothing   = request.form.get("clothing_card_number")
    notes      = request.form.get("notes")

    try:
        count = int(count)
        if count < 1:
            count = 1
    except ValueError:
        count = 1

    if catalog_id:
        catalog_entry = CatalogService.get_by_id(int(catalog_id))
        if not catalog_entry:
            flash("Nie znaleziono pozycji w katalogu.", "danger")
            return redirect(url_for("item_controller.add_item_form"))
        name  = catalog_entry.name
        unit  = catalog_entry.unit_of_measure
        usage = catalog_entry.usage_period_months
        if not notes:
            notes = catalog_entry.default_notes
    else:
        name  = request.form.get("name")
        unit  = request.form.get("unit_of_measure", "szt")
        usage = request.form.get("usage_period_months")
        usage = int(usage) if usage else None

    items = ItemService.create_bulk(
        name=name,
        unit_of_measure=unit,
        count=count,
        usage_period_months=usage,
        clothing_card_number=clothing,
        notes=notes,
        catalog_id=int(catalog_id) if catalog_id else None
    )

    if items:
        flash(f"Dodano {len(items)} szt. przedmiotu '{name}' do magazynu.", "success")
    else:
        flash("Błąd podczas dodawania przedmiotów.", "danger")

    return redirect(url_for("item_controller.items_list"))


@item_bp.route("/items/<int:id>")
@role_required()
def item_detail(id):
    item = ItemService.get_by_id(id)
    if not item:
        flash("Nie znaleziono przedmiotu.", "danger")
        return redirect(url_for("item_controller.items_list"))
    logs = ItemService.get_item_log(id)
    userCAS = session.get("CAS_USERNAME")
    return render_template("items/detail.html", item=item, logs=logs, userCAS=userCAS)


@item_bp.route("/items/<int:id>/edit", methods=["GET"])
@role_required()
def edit_item_form(id):
    item = ItemService.get_by_id(id)
    if not item:
        flash("Nie znaleziono przedmiotu.", "danger")
        return redirect(url_for("item_controller.items_list"))
    userCAS = session.get("CAS_USERNAME")
    return render_template("items/edit.html", item=item, userCAS=userCAS)


@item_bp.route("/items/<int:id>/edit", methods=["POST"])
@role_required(["manager", "admin"])
def edit_item_post(id):
    name     = request.form.get("name")
    unit     = request.form.get("unit_of_measure")
    usage    = request.form.get("usage_period_months")
    clothing = request.form.get("clothing_card_number")
    notes    = request.form.get("notes")
    usage    = int(usage) if usage else None

    item = ItemService.update(id, name=name, unit_of_measure=unit,
                               usage_period_months=usage,
                               clothing_card_number=clothing, notes=notes)
    if item:
        flash("Zapisano zmiany.", "success")
    else:
        flash("Błąd podczas zapisu.", "danger")
    return redirect(url_for("item_controller.item_detail", id=id))


@item_bp.route("/items/<int:id>/issue", methods=["GET"])
@role_required()
def issue_item_form(id):
    item = ItemService.get_by_id(id)
    if not item:
        flash("Nie znaleziono przedmiotu.", "danger")
        return redirect(url_for("item_controller.items_list"))

    sap_available = True
    sap_stock     = None
    if item.catalog_id:
        sap_available, sap_stock = ItemService.check_sap_stock(item.catalog_id)
        if not sap_available:
            flash(f"Brak stanu magazynowego w SAP (stan: {sap_stock}). Nie można wydać.", "danger")
            return redirect(url_for("item_controller.item_detail", id=id))

    firefighters = FirefighterService.get_all_active()
    return render_template(
        "items/issue.html",
        item=item,
        firefighters=firefighters,
        now=date.today().isoformat(),
        sap_stock=sap_stock
    )


@item_bp.route("/items/<int:id>/issue", methods=["POST"])
@role_required(["manager", "admin"])
def issue_item_post(id):
    firefighter_id = request.form.get("firefighter_id")
    issue_date     = request.form.get("issue_date")
    clothing       = request.form.get("clothing_card_number")
    notes          = request.form.get("notes")
    nfc_scan       = request.form.get("nfc_scan") == "true"

    if not firefighter_id or not issue_date:
        flash("Wybierz strażaka i datę wydania.", "danger")
        return redirect(url_for("item_controller.issue_item_form", id=id))

    item = ItemService.issue_item(
        item_id=id,
        firefighter_id=int(firefighter_id),
        issue_date=issue_date,
        performed_by_user_id=UserService.get_user_by_cas_username(session["CAS_USERNAME"]).user_id,
        clothing_card_number=clothing,
        notes=notes,
        nfc_scan=nfc_scan
    )

    if item:
        flash("Przedmiot został wydany.", "success")
    else:
        flash("Błąd podczas wydania przedmiotu.", "danger")
    return redirect(url_for("item_controller.item_detail", id=id))


@item_bp.route("/items/<int:id>/return", methods=["POST"])
@role_required(["manager", "admin"])
def return_item(id):
    item = ItemService.get_by_id(id)
    firefighter_id = item.firefighter_id if item else None

    result = ItemService.return_item(
        item_id=id,
        performed_by_user_id=UserService.get_user_by_cas_username(session["CAS_USERNAME"]).user_id,
        notes=request.form.get("notes")
    )

    if result:
        flash("Przedmiot zwrócono do magazynu.", "success")
    else:
        flash("Błąd podczas zwrotu.", "danger")

    if firefighter_id:
        return redirect(url_for("firefighter_controller.firefighter_detail", id=firefighter_id))
    return redirect(url_for("item_controller.items_list"))


@item_bp.route("/items/<int:id>/consume", methods=["POST"])
@role_required(["manager", "admin"])
def consume_item(id):
    item = ItemService.get_by_id(id)
    firefighter_id = item.firefighter_id if item else None

    result = ItemService.mark_consumed(
        item_id=id,
        performed_by_user_id=UserService.get_user_by_cas_username(session["CAS_USERNAME"]).user_id,
        notes=request.form.get("notes")
    )

    if result:
        flash("Przedmiot oznaczono jako zużyty.", "success")
    else:
        flash("Błąd podczas oznaczania.", "danger")

    if firefighter_id:
        return redirect(url_for("firefighter_controller.firefighter_detail", id=firefighter_id))
    return redirect(url_for("item_controller.items_list"))


@item_bp.route("/items/<int:id>/delete", methods=["POST"])
@role_required(["admin"])
def delete_item(id):
    next_url = request.form.get("next", url_for("item_controller.items_consumed"))
    result = ItemService.delete(id)
    if result:
        flash("Przedmiot został usunięty.", "success")
    else:
        flash("Błąd podczas usuwania przedmiotu.", "danger")
    return redirect(next_url)