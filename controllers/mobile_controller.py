from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from functools import wraps
from datetime import date

from services.user_service import UserService
from services.item_service import ItemService
from services.firefighter_service import FirefighterService
from services.catalog_service import CatalogService
from models.item_model import RoleRequiredItem, Item

mobile_bp = Blueprint("mobile_controller", __name__, url_prefix="/Sp/mobile")


def role_required(required_roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cas_username = session.get("CAS_USERNAME")
            if not cas_username:
                return redirect(url_for("user_controller.cas_login"))
            user = UserService.get_user_by_cas_username(cas_username)
            if not user or not user.is_active:
                return redirect(url_for("user_controller.cas_login"))
            if required_roles and user.role not in required_roles:
                return redirect(url_for("user_controller.unauthorize"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@mobile_bp.route("/")
@role_required()
def mobile_dashboard():
    from services.notification_service import NotificationService
    session.pop("force_desktop", None)
    session.pop("last_nfc_scan", None)
    counts = NotificationService.get_notifications_count()
    return render_template("mobile/dashboard.html",
                           notifications_danger=counts["danger"])


# ---------------------------------------------------------
# SCAN — jedyne miejsce gdzie resetujemy last_nfc_scan
# ---------------------------------------------------------
@mobile_bp.route("/scan")
@role_required()
def mobile_scan():
    session.pop("last_nfc_scan", None)
    firefighters = FirefighterService.get_all_active()
    return render_template("mobile/scan.html", firefighters=firefighters)


# ---------------------------------------------------------
# LISTA STRAŻAKÓW (mobilna)
# ---------------------------------------------------------

@mobile_bp.route("/firefighters")
@role_required()
def mobile_firefighters():
    from services.notification_service import NotificationService
    firefighters = FirefighterService.get_all_active()
    return render_template("mobile/firefighters.html", firefighters=firefighters)


# ---------------------------------------------------------
# POWIADOMIENIA (mobilne)
# ---------------------------------------------------------

@mobile_bp.route("/notifications")
@role_required()
def mobile_notifications():
    from services.notification_service import NotificationService
    notifications = NotificationService.get_notifications()
    counts        = NotificationService.get_notifications_count()
    return render_template("mobile/notifications.html",
                           notifications=notifications,
                           counts=counts)
    
    
# ---------------------------------------------------------
# FIREFIGHTER — korzysta tylko z sesji, bez request.args
# ---------------------------------------------------------
@mobile_bp.route("/firefighter/<int:firefighter_id>")
@role_required()
def mobile_firefighter(firefighter_id):
    firefighter = FirefighterService.get_by_id(firefighter_id)
    if not firefighter:
        flash("Nie znaleziono strażaka.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    # Informacja czy wejście nastąpiło po skanie NFC
    nfc_scan = session.get("last_nfc_scan", False)

    issued_items = FirefighterService.get_issued_items(firefighter_id)

    required_items = RoleRequiredItem.query.filter_by(
        role=firefighter.role,
        is_required=True
    ).all()

    issued_catalog_ids = {
        item.catalog_id for item in issued_items if item.catalog_id
    }

    equipment_status = []
    for req in required_items:
        equipment_status.append({
            "name":       req.catalog_item.name,
            "quantity":   req.quantity,
            "catalog_id": req.catalog_id,
            "has_it":     req.catalog_id in issued_catalog_ids,
        })

    catalog = CatalogService.get_all_active()
    missing_count = sum(1 for e in equipment_status if not e["has_it"])

    return render_template(
        "mobile/firefighter.html",
        firefighter=firefighter,
        equipment_status=equipment_status,
        issued_items=issued_items,
        catalog=catalog,
        missing_count=missing_count,
        nfc_scan=nfc_scan,
        today=date.today().isoformat()
    )


# ---------------------------------------------------------
# CONFIRM — korzysta z sesji
# ---------------------------------------------------------
@mobile_bp.route("/confirm", methods=["POST"])
@role_required()
def mobile_confirm():
    firefighter_id = request.form.get("firefighter_id")
    catalog_id     = request.form.get("catalog_id")
    nfc_scan       = session.get("last_nfc_scan", False)

    if not firefighter_id or not catalog_id:
        flash("Brakuje danych do wydania.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    firefighter   = FirefighterService.get_by_id(int(firefighter_id))
    catalog_entry = CatalogService.get_by_id(int(catalog_id))

    if not firefighter or not catalog_entry:
        flash("Nie znaleziono strażaka lub przedmiotu.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    return render_template(
        "mobile/confirm_issue.html",
        firefighter=firefighter,
        catalog_entry=catalog_entry,
        nfc_scan=nfc_scan,
        today=date.today().isoformat()
    )


# ---------------------------------------------------------
# ISSUE — po wydaniu resetujemy last_nfc_scan (pop)
# ---------------------------------------------------------
@mobile_bp.route("/issue", methods=["POST"])
@role_required(["manager", "admin"])
def mobile_issue():
    firefighter_id = int(request.form.get("firefighter_id"))
    catalog_id     = int(request.form.get("catalog_id"))
    issue_date     = request.form.get("issue_date")
    clothing       = request.form.get("clothing_card_number")
    notes          = request.form.get("notes")
    nfc_scan       = session.pop("last_nfc_scan", False)

    user          = UserService.get_user_by_cas_username(session["CAS_USERNAME"])
    firefighter   = FirefighterService.get_by_id(firefighter_id)
    catalog_entry = CatalogService.get_by_id(catalog_id)

    if not firefighter or not catalog_entry:
        flash("Nie znaleziono strażaka lub przedmiotu.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    # Pobierz istniejący przedmiot z magazynu
    item = Item.query.filter_by(
        catalog_id=catalog_id,
        is_consumed=False,
        firefighter_id=None
    ).first()

    if not item:
        flash(f"Brak '{catalog_entry.name}' w magazynie.", "danger")
        return redirect(url_for("mobile_controller.mobile_firefighter",
                                firefighter_id=firefighter_id))

    item = ItemService.issue_item(
        item_id=item.item_id,
        firefighter_id=firefighter_id,
        issue_date=issue_date,
        performed_by_user_id=user.user_id,
        clothing_card_number=clothing,
        notes=notes,
        nfc_scan=nfc_scan
    )

    if item:
        return render_template(
            "mobile/success.html",
            item=item,
            firefighter=firefighter,
            firefighter_id=firefighter_id
        )
    else:
        flash("Błąd podczas wydania przedmiotu.", "danger")
        return redirect(url_for("mobile_controller.mobile_firefighter",
                                firefighter_id=firefighter_id))

# ---------------------------------------------------------
# API — jedyne miejsce gdzie ustawiamy last_nfc_scan
# ---------------------------------------------------------
@mobile_bp.route("/api/firefighter-by-nfc/<nfc_hash>")
@role_required()
def api_firefighter_by_nfc(nfc_hash):
    ff = FirefighterService.get_by_nfc_hash(nfc_hash)
    if not ff:
        return jsonify({"error": "Nie znaleziono"}), 404

    # Ustawiamy flagę NFC TYLKO tutaj
    session["last_nfc_scan"] = True
    session.modified = True

    return jsonify({
        "id":        ff.firefighter_id,
        "full_name": ff.full_name,
        "role":      ff.role_label
    })
