from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    make_response,
    g
)

from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
    get_jwt_identity
)

from flask_jwt_extended.exceptions import (
    NoAuthorizationError,
    JWTExtendedException
)

from functools import wraps

from services.user_service import UserService, _normalize_nfc


auth_mobile_bp = Blueprint(
    "auth_mobile",
    __name__,
    url_prefix="/zsr/mobile"
)


# ────────────────────────────────────────────────
# Dekorator logowania mobilnego
# ────────────────────────────────────────────────
def mobile_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request(locations=["cookies"])

            user_id = get_jwt_identity()

            user = UserService.get_user_by_id(
                int(user_id)
            )

            if not user or not user.is_active:
                raise JWTExtendedException(
                    "User not found or inactive"
                )

            g.mobile_user = user

        except (
            NoAuthorizationError,
            JWTExtendedException,
            Exception
        ):
            if request.method == "GET":
                return redirect(
                    url_for(
                        "auth_mobile.mobile_login_page"
                    )
                )

            return jsonify({
                "success": False,
                "error": "Unauthorized"
            }), 401

        return fn(*args, **kwargs)

    return wrapper


# ────────────────────────────────────────────────
# Strona logowania
# ────────────────────────────────────────────────
@auth_mobile_bp.route("/login", methods=["GET"])
def mobile_login_page():
    return render_template("mobile/login.html")


# ────────────────────────────────────────────────
# Logowanie NFC
# ────────────────────────────────────────────────
@auth_mobile_bp.route("/login/nfc", methods=["POST"])
def mobile_login_nfc():

    data = request.get_json(silent=True) or {}

    raw_uid = (
        data.get("card_uid")
        or data.get("nfc_hash")
        or ""
    ).strip()

    if not raw_uid:
        return jsonify({
            "success": False,
            "error": "Brak danych karty NFC."
        }), 400

    normalized = _normalize_nfc(raw_uid)

    print(f"[NFC LOGIN] raw='{raw_uid}' → normalized='{normalized}'")

    user = UserService.get_user_by_nfc_hash(normalized)

    if not user:
        print(f"[NFC LOGIN] Nie znaleziono użytkownika dla UID: {normalized}")
        return jsonify({
            "success": False,
            "error": "Nieznana karta lub konto nieaktywne."
        }), 401

    if not user.is_active:
        print(f"[NFC LOGIN] Konto nieaktywne: {user.user_id}")
        return jsonify({
            "success": False,
            "error": "Konto nieaktywne."
        }), 401

    print(f"[NFC LOGIN] OK — user_id={user.user_id} '{user.full_name_or_username}'")

    access_token = create_access_token(
        identity=str(user.user_id)
    )

    resp = jsonify({
        "success": True,
        "user_id": user.user_id,
        "full_name": user.full_name_or_username,
        "role": user.role,
        "redirect_url": url_for(
            "mobile_controller.mobile_dashboard"
        ),
    })

    set_access_cookies(resp, access_token)

    return resp, 200


# ────────────────────────────────────────────────
# Wylogowanie
# ────────────────────────────────────────────────
@auth_mobile_bp.route("/logout", methods=["GET", "POST"])
def mobile_logout():

    resp = make_response(
        redirect(
            url_for(
                "auth_mobile.mobile_login_page"
            )
        )
    )

    unset_jwt_cookies(resp)

    return resp