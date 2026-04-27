from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from functools import wraps

from services.user_service import UserService
from services.firefighter_service import FirefighterService

firefighter_bp = Blueprint("firefighter_controller", __name__, url_prefix="/Sp")


# ---------------------------------------------------------
# Dekorator role_required
# ---------------------------------------------------------

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
# LISTA STRAŻAKÓW
# ---------------------------------------------------------

@firefighter_bp.route("/firefighters")
@role_required()
def firefighters_list():
    firefighters = FirefighterService.get_all_active()
    return render_template("firefighters/list.html", firefighters=firefighters)


# ---------------------------------------------------------
# DODAWANIE STRAŻAKA
# ---------------------------------------------------------

@firefighter_bp.route("/firefighters/add", methods=["GET"])
@role_required()
def add_firefighter_form():
    return render_template("firefighters/add.html")


@firefighter_bp.route("/firefighters/add", methods=["POST"])
@role_required(["manager", "admin"])
def add_firefighter_post():
    first_name   = request.form.get("first_name")
    last_name    = request.form.get("last_name")
    nfc_username = request.form.get("nfc_username")
    nfc_hash     = request.form.get("nfc_hash")

    # Sprawdź duplikat NFC przed dodaniem
    if nfc_hash:
        existing = FirefighterService.get_by_nfc_hash(nfc_hash)
        if existing:
            flash(f"Ta karta NFC jest już przypisana do strażaka: {existing.full_name}.", "danger")
            return redirect(url_for("firefighter_controller.add_firefighter_form"))

    def to_int(val):
        try: return int(val) if val else None
        except: return None

    def to_float(val):
        try: return float(val) if val else None
        except: return None

    firefighter = FirefighterService.create(
        first_name=first_name,
        last_name=last_name,
        nfc_username=nfc_username or None,
        nfc_hash=nfc_hash or None,
        height_cm=to_int(request.form.get("height_cm")),
        chest_cm=to_int(request.form.get("chest_cm")),
        waist_cm=to_int(request.form.get("waist_cm")),
        hat_size=to_float(request.form.get("hat_size")),
        shirt_size=request.form.get("shirt_size") or None,
        shoe_size=to_float(request.form.get("shoe_size")),
    )

    if firefighter:
        flash("Strażak został dodany.", "success")
    else:
        flash("Błąd podczas dodawania strażaka.", "danger")

    return redirect(url_for("firefighter_controller.firefighters_list"))


# ---------------------------------------------------------
# SZCZEGÓŁY STRAŻAKA
# ---------------------------------------------------------

@firefighter_bp.route("/firefighters/<int:id>")
@role_required()
def firefighter_detail(id):
    firefighter = FirefighterService.get_by_id(id)
    if not firefighter:
        flash("Nie znaleziono strażaka.", "danger")
        return redirect(url_for("firefighter_controller.firefighters_list"))

    issued_items = FirefighterService.get_issued_items(id)
    return render_template(
        "firefighters/detail.html",
        firefighter=firefighter,
        issued_items=issued_items
    )


# ---------------------------------------------------------
# EDYCJA STRAŻAKA
# ---------------------------------------------------------

@firefighter_bp.route("/firefighters/<int:id>/edit", methods=["GET"])
@role_required()
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

    def to_int(val):
        try: return int(val) if val else None
        except: return None

    def to_float(val):
        try: return float(val) if val else None
        except: return None

    # Obsługa NFC – sprawdź duplikat
    if nfc_hash:
        existing = FirefighterService.get_by_nfc_hash(nfc_hash)
        if existing and existing.firefighter_id != id:
            # Duplikat – zwróć JSON jeśli request AJAX, flash jeśli zwykły
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "error": "duplicate",
                    "message": f"Ta karta NFC jest już przypisana do strażaka: {existing.full_name}."
                }), 409
            flash(f"Ta karta NFC jest już przypisana do strażaka: {existing.full_name}.", "danger")
            return redirect(url_for("firefighter_controller.edit_firefighter_form", id=id))

        result = FirefighterService.attach_nfc(id, nfc_username, nfc_hash)
        if result is None:
            flash("Błąd podczas przypisywania karty NFC.", "danger")
            return redirect(url_for("firefighter_controller.edit_firefighter_form", id=id))

    firefighter = FirefighterService.update(
        id,
        first_name=first_name,
        last_name=last_name,
        height_cm=to_int(request.form.get("height_cm")),
        chest_cm=to_int(request.form.get("chest_cm")),
        waist_cm=to_int(request.form.get("waist_cm")),
        hat_size=to_float(request.form.get("hat_size")),
        shirt_size=request.form.get("shirt_size") or None,
        shoe_size=to_float(request.form.get("shoe_size")),
    )

    if firefighter:
        flash("Zapisano zmiany.", "success")
    else:
        flash("Błąd podczas zapisu.", "danger")

    return redirect(url_for("firefighter_controller.firefighter_detail", id=id))


# ---------------------------------------------------------
# DEAKTYWACJA STRAŻAKA
# ---------------------------------------------------------

@firefighter_bp.route("/firefighters/<int:id>/deactivate", methods=["POST"])
@role_required(["manager", "admin"])
def deactivate_firefighter(id):
    ok = FirefighterService.deactivate(id)
    if ok:
        flash("Strażak został dezaktywowany.", "success")
    else:
        flash("Błąd podczas dezaktywacji.", "danger")
    return redirect(url_for("firefighter_controller.firefighters_list"))


# ---------------------------------------------------------
# USUWANIE STRAŻAKA
# ---------------------------------------------------------

@firefighter_bp.route("/firefighters/<int:id>/delete", methods=["POST"])
@role_required(["admin"])
def delete_firefighter(id):
    result = FirefighterService.delete(id)
    if result:
        flash("Strażak został usunięty.", "success")
    else:
        flash("Nie można usunąć – strażak ma wydane przedmioty.", "danger")
    return redirect(url_for("firefighter_controller.firefighters_list"))


# ---------------------------------------------------------
# API: WYSZUKIWANIE STRAŻAKA PO NFC
# ---------------------------------------------------------

@firefighter_bp.route("/api/firefighters/by-nfc/<nfc_hash>")
@role_required()
def api_firefighter_by_nfc(nfc_hash):
    firefighter = FirefighterService.get_by_nfc_hash(nfc_hash)
    if not firefighter:
        return jsonify({"error": "Nie znaleziono"}), 404
    return jsonify({
        "id": firefighter.firefighter_id,
        "full_name": firefighter.full_name
    })