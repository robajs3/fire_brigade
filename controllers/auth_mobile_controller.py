from flask import Blueprint, render_template, request, redirect, url_for, jsonify, make_response
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies, verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError, JWTExtendedException
from functools import wraps
from flask import g

from services.user_service import UserService

auth_mobile_bp = Blueprint("auth_mobile", __name__, url_prefix="/zsr/mobile")


# ─── Dekorator ───────────────────────────────────────────
def mobile_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=["cookies"])
            user_id = get_jwt_identity()
            user = UserService.get_user_by_id(int(user_id))
            if not user or not user.is_active:
                raise JWTExtendedException("User not found or inactive")
            g.mobile_user = user
        except (NoAuthorizationError, JWTExtendedException, Exception):
            if request.method == "GET":
                return redirect(url_for("auth_mobile.mobile_login_page"))
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


# ─── Strona logowania ─────────────────────────────────────
@auth_mobile_bp.route("/login", methods=["GET"])
def mobile_login_page():
    return render_template("mobile/login.html")


# ─── Logowanie przez NFC ──────────────────────────────────
@auth_mobile_bp.route("/login/nfc", methods=["POST"])
def mobile_login_nfc():
    data     = request.get_json(silent=True) or {}
    nfc_hash = data.get("nfc_hash", "").strip()

    if not nfc_hash:
        return jsonify({"success": False, "error": "Brak danych karty NFC."}), 400

    user = UserService.get_user_by_nfc_hash(nfc_hash)
    if not user or not user.is_active:
        return jsonify({"success": False, "error": "Nieznana karta lub konto nieaktywne."}), 401

    access_token = create_access_token(identity=str(user.user_id))
    resp = jsonify({
        "success":   True,
        "user_id":   user.user_id,
        "full_name": user.full_name_or_username,
        "role":      user.role,
    })
    set_access_cookies(resp, access_token)
    return resp, 200


# ─── Wylogowanie ─────────────────────────────────────────
@auth_mobile_bp.route("/logout", methods=["GET", "POST"])
def mobile_logout():
    resp = make_response(redirect(url_for("auth_mobile.mobile_login_page")))
    unset_jwt_cookies(resp)
    return resp