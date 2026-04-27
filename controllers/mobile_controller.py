 # controllers/mobile_controller.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from functools import wraps
from datetime import date

from cas_auth import login_required
from services.user_service import UserService
from services.item_service import ItemService
from services.firefighter_service import FirefighterService

mobile_bp = Blueprint("mobile_controller", __name__, url_prefix="/Sp/mobile")


# ---------------------------------------------------------
# Dekorator role_required (mobilny)
# ---------------------------------------------------------

def role_required(required_roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cas_username = session.get("CAS_USERNAME")
            if not cas_username:
                return redirect(url_for("mobile_controller.mobile_login"))

            user = UserService.get_user_by_cas_username(cas_username)
            if not user or not user.is_active:
                return redirect(url_for("mobile_controller.mobile_login"))

            if required_roles and user.role not in required_roles:
                return redirect(url_for("mobile_controller.mobile_login"))

            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------
# LOGIN MOBILNY
# ---------------------------------------------------------

@mobile_bp.route("/login")
def mobile_login():
    if session.get("CAS_USERNAME"):
        return redirect(url_for("mobile_controller.mobile_dashboard"))
    cas_server = __import__("flask").current_app.config["CAS_SERVER"]
    service_url = url_for("user_controller.cas_login", _external=True)
    return redirect(f"{cas_server}/login?service={service_url}"
                    + f"&next={url_for('mobile_controller.mobile_dashboard', _external=True)}")


# ---------------------------------------------------------
# DASHBOARD MOBILNY
# ---------------------------------------------------------

@mobile_bp.route("/")
@role_required()
def mobile_dashboard():
    in_stock = ItemService.get_all_in_stock()
    return render_template(
        "mobile/dashboard.html",
        in_stock_count=len(in_stock),
        items=in_stock
    )


# ---------------------------------------------------------
# EKRAN SKANOWANIA – wybór przedmiotu + skan NFC
# ---------------------------------------------------------

@mobile_bp.route("/scan")
@role_required()
def mobile_scan():
    items = ItemService.get_all_in_stock()
    return render_template("mobile/scan.html", items=items)


@mobile_bp.route("/scan/<int:item_id>")
@role_required()
def mobile_scan_item(item_id):
    item = ItemService.get_by_id(item_id)
    if not item or item.is_consumed or item.firefighter_id:
        flash("Przedmiot niedostępny.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))
    return render_template("mobile/scan.html", items=ItemService.get_all_in_stock(), selected_item=item)


# ---------------------------------------------------------
# POTWIERDZENIE WYDANIA
# ---------------------------------------------------------

@mobile_bp.route("/confirm", methods=["POST"])
@role_required()
def mobile_confirm():
    item_id       = request.form.get("item_id")
    firefighter_id = request.form.get("firefighter_id")
    nfc_scan      = request.form.get("nfc_scan", "false") == "true"

    if not item_id or not firefighter_id:
        flash("Brakuje danych do wydania.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    item        = ItemService.get_by_id(int(item_id))
    firefighter = FirefighterService.get_by_id(int(firefighter_id))

    if not item or not firefighter:
        flash("Nie znaleziono przedmiotu lub strażaka.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    return render_template(
        "mobile/confirm_issue.html",
        item=item,
        firefighter=firefighter,
        nfc_scan=nfc_scan,
        today=date.today().isoformat()
    )


# ---------------------------------------------------------
# WYKONANIE WYDANIA
# ---------------------------------------------------------

@mobile_bp.route("/issue", methods=["POST"])
@role_required(["manager", "admin"])
def mobile_issue():
    item_id        = request.form.get("item_id")
    firefighter_id = request.form.get("firefighter_id")
    issue_date     = request.form.get("issue_date")
    clothing       = request.form.get("clothing_card_number")
    notes          = request.form.get("notes")
    nfc_scan       = request.form.get("nfc_scan", "false") == "true"

    user = UserService.get_user_by_cas_username(session["CAS_USERNAME"])

    item = ItemService.issue_item(
        item_id=int(item_id),
        firefighter_id=int(firefighter_id),
        issue_date=issue_date,
        performed_by_user_id=user.user_id,
        clothing_card_number=clothing,
        notes=notes,
        nfc_scan=nfc_scan
    )

    if item:
        firefighter = FirefighterService.get_by_id(int(firefighter_id))
        return render_template(
            "mobile/success.html",
            item=item,
            firefighter=firefighter
        )
    else:
        flash("Błąd podczas wydania przedmiotu.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))


# ---------------------------------------------------------
# API – strażak po NFC hash (używane przez JS na tablecie)
# ---------------------------------------------------------

@mobile_bp.route("/api/firefighter-by-nfc/<nfc_hash>")
@role_required()
def api_firefighter_by_nfc(nfc_hash):
    ff = FirefighterService.get_by_nfc_hash(nfc_hash)
    if not ff:
        return jsonify({"error": "Nie znaleziono"}), 404
    return jsonify({"id": ff.firefighter_id, "full_name": ff.full_name})