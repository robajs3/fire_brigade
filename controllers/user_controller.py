from flask import Blueprint, render_template, session, redirect, url_for, request, flash, current_app
from functools import wraps

from cas_auth import login_required, validate_ticket
from services.user_service import UserService

user_bp = Blueprint("user_controller", __name__, url_prefix="/zsr")


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
# CAS LOGIN / LOGOUT
# ---------------------------------------------------------

@user_bp.route("/cas/login")
def cas_login():
    ticket = request.args.get("ticket")
    service_url = url_for("user_controller.cas_login", _external=True)

    if ticket:
        username = validate_ticket(ticket, service_url)
        if username:
            session["CAS_USERNAME"] = username
            UserService.ensure_user_exists(username)
            return redirect(url_for("dashboard_controller.dashboard"))
        flash("Błąd uwierzytelniania CAS.", "danger")
        return redirect(url_for("user_controller.unauthorize"))

    cas_server = current_app.config["CAS_SERVER"]
    return redirect(f"{cas_server}/login?service={service_url}")


@user_bp.route("/logout")
def logout():
    session.clear()
    service_url = url_for("user_controller.cas_login", _external=True)
    cas_server = current_app.config["CAS_SERVER"]
    return redirect(f"{cas_server}/logout?service={service_url}")


# ---------------------------------------------------------
# UNAUTHORIZE
# ---------------------------------------------------------

@user_bp.route("/unauthorize")
def unauthorize():
    return render_template("users/unauthorize.html")


# ---------------------------------------------------------
# PROFIL
# ---------------------------------------------------------

@user_bp.route("/profile")
@login_required
@role_required()
def profile():
    user = UserService.get_user_by_cas_username(session["CAS_USERNAME"])
    return render_template("users/profile.html", user=user)


# ---------------------------------------------------------
# LISTA UŻYTKOWNIKÓW (ADMIN)
# ---------------------------------------------------------

@user_bp.route("/users")
@login_required
@role_required(["admin"])
def users_list():
    users = UserService.get_all_users()  # ← wszyscy, nie tylko aktywni
    return render_template("users/list.html", users=users)


# ---------------------------------------------------------
# DODAWANIE UŻYTKOWNIKA (ADMIN)
# ---------------------------------------------------------

@user_bp.route("/users/add", methods=["GET"])
@login_required
@role_required(["admin"])
def add_user_form():
    return render_template("users/add.html")


@user_bp.route("/users/add", methods=["POST"])
@login_required
@role_required(["admin"])
def add_user_post():
    cas_username = request.form.get("cas_username")
    full_name    = request.form.get("full_name")
    role         = request.form.get("role", "viewer")

    user = UserService.create_user(cas_username, full_name, role)
    if user:
        flash("Użytkownik został dodany.", "success")
    else:
        flash("Błąd podczas dodawania użytkownika.", "danger")

    return redirect(url_for("user_controller.users_list"))


# ---------------------------------------------------------
# EDYCJA UŻYTKOWNIKA (ADMIN)
# ---------------------------------------------------------

@user_bp.route("/users/<int:id>/edit", methods=["GET"])
@login_required
@role_required(["admin"])
def edit_user_form(id):
    user = UserService.get_user_by_id(id)
    if not user:
        flash("Nie znaleziono użytkownika.", "danger")
        return redirect(url_for("user_controller.users_list"))
    return render_template("users/edit.html", user=user)


@user_bp.route("/users/<int:id>/edit", methods=["POST"])
@login_required
@role_required(["admin"])
def edit_user_post(id):
    full_name = request.form.get("full_name")
    role      = request.form.get("role")
    is_active = request.form.get("is_active") == "on"

    user = UserService.update_user(id, full_name=full_name, role=role, is_active=is_active)
    if user:
        flash("Zapisano zmiany.", "success")
    else:
        flash("Błąd podczas zapisu.", "danger")

    return redirect(url_for("user_controller.users_list"))


# ---------------------------------------------------------
# TOGGLE AKTYWNOŚCI (ADMIN)
# ---------------------------------------------------------

@user_bp.route("/users/<int:id>/toggle", methods=["POST"])
@login_required
@role_required(["admin"])
def toggle_user(id):
    user = UserService.get_user_by_id(id)
    if not user:
        flash("Nie znaleziono użytkownika.", "danger")
        return redirect(url_for("user_controller.users_list"))

    # Zabezpieczenie – nie można wyłączyć samego siebie
    if user.cas_username == session.get("CAS_USERNAME"):
        flash("Nie możesz wyłączyć własnego konta.", "warning")
        return redirect(url_for("user_controller.users_list"))

    new_state = not user.is_active
    updated = UserService.update_user(id, is_active=new_state)
    if updated:
        status = "włączony" if new_state else "wyłączony"
        flash(f"Użytkownik {user.cas_username} został {status}.", "success")
    else:
        flash("Błąd podczas zmiany statusu.", "danger")

    return redirect(url_for("user_controller.users_list"))


# ---------------------------------------------------------
# USUWANIE UŻYTKOWNIKA (ADMIN)
# ---------------------------------------------------------

@user_bp.route("/users/<int:id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def delete_user(id):
    user = UserService.get_user_by_id(id)
    if not user:
        flash("Nie znaleziono użytkownika.", "danger")
        return redirect(url_for("user_controller.users_list"))

    # Zabezpieczenie – nie można usunąć samego siebie
    if user.cas_username == session.get("CAS_USERNAME"):
        flash("Nie możesz usunąć własnego konta.", "warning")
        return redirect(url_for("user_controller.users_list"))

    result = UserService.delete_user(id)
    if result:
        flash("Użytkownik został usunięty.", "success")
    else:
        flash("Błąd podczas usuwania użytkownika.", "danger")

    return redirect(url_for("user_controller.users_list"))

@user_bp.route("/users/<int:id>/assign-nfc", methods=["POST"])
@login_required
@role_required(["admin"])
def assign_nfc_to_user(id):
    nfc_hash = request.form.get("nfc_hash", "").strip()

    if not nfc_hash:
        flash("Brak danych karty NFC.", "danger")
        return redirect(url_for("user_controller.users_list"))

    existing = UserService.get_user_by_nfc_hash(nfc_hash)
    if existing and existing.user_id != id:
        flash(f"Ta karta jest już przypisana do: {existing.full_name_or_username}.", "danger")
        return redirect(url_for("user_controller.users_list"))

    result = UserService.update_user(id, nfc_hash=nfc_hash)
    if result:
        flash("Karta NFC została przypisana.", "success")
    else:
        flash("Błąd podczas przypisywania karty NFC.", "danger")

    return redirect(url_for("user_controller.users_list"))


@user_bp.route("/users/<int:id>/remove-nfc", methods=["POST"])
@login_required
@role_required(["admin"])
def remove_nfc_from_user(id):
    result = UserService.update_user(id, nfc_hash="")
    if result:
        flash("Karta NFC została usunięta.", "success")
    else:
        flash("Błąd podczas usuwania karty NFC.", "danger")
    return redirect(url_for("user_controller.users_list"))

# ---------------------------------------------------------
# DEV LOGIN (tylko debug=True)
# ---------------------------------------------------------

@user_bp.route("/dev-login")
def dev_login():
    if not current_app.debug:
        return redirect(url_for("user_controller.unauthorize"))

    session["CAS_USERNAME"] = "dev_admin"
    user = UserService.ensure_user_exists("dev_admin", "Dev Administrator")
    # Dev admin zawsze ma rolę admin
    if user and user.role != "admin":
        UserService.update_user(user.user_id, role="admin")

    flash("Zalogowano jako dev_admin (tryb developerski).", "info")
    return redirect(url_for("dashboard_controller.dashboard"))