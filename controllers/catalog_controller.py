from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from functools import wraps

from services.user_service import UserService
from services.catalog_service import CatalogService
from models.item_model import RoleRequiredItem
from models.firefighter_model import Firefighter

catalog_bp = Blueprint("catalog_controller", __name__, url_prefix="/zsr")

# Role techniczne (klucze)
ROLES = ["kierownik_gbr", "strazak", "ratownik_medyczny"]


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


# ---------------------------------------------------------
# LISTA
# ---------------------------------------------------------

@catalog_bp.route("/catalog")
@role_required()
def catalog_list():
    entries = CatalogService.get_all()
    return render_template("catalog/list.html", entries=entries)


# ---------------------------------------------------------
# RĘCZNA SYNCHRONIZACJA STANU Z SAP
# ---------------------------------------------------------

@catalog_bp.route("/catalog/sync-sap", methods=["POST"])
@role_required(["admin"])
def sync_sap():
    from services.sap_service import SAPService
    result = SAPService.sync_stock_to_catalog()
    flash(
        f"Synchronizacja SAP zakończona: "
        f"zaktualizowano {result['updated']}, "
        f"utworzono {result['created']} nowych pozycji "
        f"(łącznie {result['total']}).",
        "success"
    )
    return redirect(url_for("item_controller.items_list"))

@catalog_bp.route("/catalog/sap-stock-preview")
@role_required(["admin"])
def sap_stock_preview():
    from services.sap_service import SAPService
    stock = SAPService.get_stock()
    return render_template("catalog/sap_preview.html", stock=stock)
# ---------------------------------------------------------
# DODAWANIE
# ---------------------------------------------------------

@catalog_bp.route("/catalog/add", methods=["GET"])
@role_required(["manager", "admin"])
def add_catalog_form():
    return render_template(
        "catalog/add.html",
        roles=ROLES,
        role_labels=Firefighter.ROLES
    )


@catalog_bp.route("/catalog/add", methods=["POST"])
@role_required(["manager", "admin"])
def add_catalog_post():
    name  = request.form.get("name")
    unit  = request.form.get("unit_of_measure", "szt")
    usage = request.form.get("usage_period_months")
    notes = request.form.get("default_notes")
    usage = int(usage) if usage else None

    # Pola SAP
    sap_matnr = request.form.get("sap_matnr") or None
    sap_kostl = request.form.get("sap_kostl") or None

    entry = CatalogService.create(
        name=name,
        unit_of_measure=unit,
        usage_period_months=usage,
        default_notes=notes,
        sap_matnr=sap_matnr,
        sap_kostl=sap_kostl
    )

    if entry:
        role_data = _parse_role_form(request.form)
        CatalogService.set_role_requirements(entry.catalog_id, role_data)
        flash("Dodano pozycję do katalogu.", "success")
    else:
        flash("Błąd podczas dodawania.", "danger")

    return redirect(url_for("catalog_controller.catalog_list"))


# ---------------------------------------------------------
# EDYCJA
# ---------------------------------------------------------

@catalog_bp.route("/catalog/<int:id>/edit", methods=["GET"])
@role_required(["manager", "admin"])
def edit_catalog_form(id):
    entry = CatalogService.get_by_id(id)
    if not entry:
        flash("Nie znaleziono pozycji.", "danger")
        return redirect(url_for("catalog_controller.catalog_list"))

    requirements = {
        r.role: r
        for r in CatalogService.get_role_requirements(id)
    }

    return render_template(
        "catalog/edit.html",
        entry=entry,
        roles=ROLES,
        role_labels=Firefighter.ROLES,
        requirements=requirements
    )


@catalog_bp.route("/catalog/<int:id>/edit", methods=["POST"])
@role_required(["manager", "admin"])
def edit_catalog_post(id):
    name      = request.form.get("name")
    unit      = request.form.get("unit_of_measure", "szt")
    usage     = request.form.get("usage_period_months")
    notes     = request.form.get("default_notes")
    is_active = request.form.get("is_active") == "on"
    usage     = int(usage) if usage else None

    # Pola SAP
    sap_matnr = request.form.get("sap_matnr") or None
    sap_kostl = request.form.get("sap_kostl") or None

    entry = CatalogService.update(
        id,
        name=name,
        unit_of_measure=unit,
        usage_period_months=usage,
        default_notes=notes,
        is_active=is_active,
        sap_matnr=sap_matnr,
        sap_kostl=sap_kostl
    )

    if entry:
        role_data = _parse_role_form(request.form)
        CatalogService.set_role_requirements(id, role_data)
        flash("Zapisano zmiany.", "success")
    else:
        flash("Błąd podczas zapisu.", "danger")

    return redirect(url_for("catalog_controller.catalog_list"))


# ---------------------------------------------------------
# USUWANIE
# ---------------------------------------------------------

@catalog_bp.route("/catalog/<int:id>/delete", methods=["POST"])
@role_required(["admin"])
def delete_catalog(id):
    result = CatalogService.delete(id)
    if result:
        flash("Usunięto pozycję z katalogu.", "success")
    else:
        flash("Nie można usunąć – pozycja ma powiązane przedmioty w magazynie.", "danger")
    return redirect(url_for("catalog_controller.catalog_list"))


# ---------------------------------------------------------
# PARSER FORMULARZA RÓL
# ---------------------------------------------------------

def _parse_role_form(form):
    """
    Oczekuje pól:
    role_strazak=on
    qty_strazak=1
    req_strazak=required
    """
    result = []
    for role in ROLES:
        if form.get(f"role_{role}"):
            result.append({
                "role": role,
                "quantity": int(form.get(f"qty_{role}", 1)),
                "is_required": form.get(f"req_{role}") == "required"
            })
    return result
