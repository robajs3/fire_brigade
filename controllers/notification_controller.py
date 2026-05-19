from flask import Blueprint, render_template, session, redirect, url_for, jsonify
from functools import wraps

from services.user_service import UserService
from services.notification_service import NotificationService

notification_bp = Blueprint("notification_controller", __name__, url_prefix="/zsr")


# ---------------------------------------------------------
# Dekorator role_required
# ---------------------------------------------------------

def role_required(required_roles=None):
    """
    required_roles = None → minimalna rola: aktywny użytkownik (viewer)
    """
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
# LISTA POWIADOMIEŃ
# ---------------------------------------------------------

@notification_bp.route("/notifications")
@role_required()
def notifications_list():
    notifications = NotificationService.get_notifications()
    counts = NotificationService.get_notifications_count()

    # Grupowanie wg severity
    grouped = {
        "danger": [n for n in notifications if n["severity"] == "danger"],
        "warning": [n for n in notifications if n["severity"] == "warning"],
        "info": [n for n in notifications if n["severity"] == "info"],
    }

    userCAS = session.get("CAS_USERNAME")

    return render_template(
        "notifications/list.html",
        notifications=notifications,
        grouped=grouped,
        counts=counts,
        userCAS=userCAS
    )


# ---------------------------------------------------------
# API: LICZNIK POWIADOMIEŃ
# ---------------------------------------------------------

@notification_bp.route("/api/notifications/count")
@role_required()
def api_notifications_count():
    counts = NotificationService.get_notifications_count()
    return jsonify(counts)
