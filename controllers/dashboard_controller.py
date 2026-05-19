from flask import Blueprint, render_template, session, redirect, url_for
from functools import wraps
from services.user_service import UserService
from services.item_service import ItemService
from services.firefighter_service import FirefighterService
from services.notification_service import NotificationService
from models.user_model import db
from models.item_model import IssuanceLog, Item
from models.firefighter_model import Firefighter

dashboard_bp = Blueprint("dashboard_controller", __name__, url_prefix="/zsr")


# ---------------------------------------------------------
# Dekorator role_required (wystarczy aktywny użytkownik)
# ---------------------------------------------------------

def role_required():
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cas_username = session.get("CAS_USERNAME")
            if not cas_username:
                return redirect(url_for("user_controller.cas_login"))
            user = UserService.get_user_by_cas_username(cas_username)
            if not user or not user.is_active:
                return redirect(url_for("auth_bp.index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@dashboard_bp.route("/")
@role_required()
def dashboard():
    cas_username = session.get("CAS_USERNAME")
    user = UserService.get_user_by_cas_username(cas_username)

    # Statystyki
    in_stock_count    = len(ItemService.get_all_in_stock())
    issued_count      = len(ItemService.get_all_issued())
    consumed_count    = len(ItemService.get_all_consumed())
    firefighters_count = len(FirefighterService.get_all_active())

    notifications = NotificationService.get_notifications_count()
    notifications_danger = notifications["danger"]

    # Ostatnie 5 operacji magazynowych
    recent_activity = (
        db.session.query(IssuanceLog, Item, Firefighter)
        .join(Item, IssuanceLog.item_id == Item.item_id)
        .outerjoin(Firefighter, IssuanceLog.firefighter_id == Firefighter.firefighter_id)
        .order_by(IssuanceLog.performed_at.desc())
        .limit(7)
        .all()
    )

    return render_template(
        "dashboard.html",
        userCAS=user,
        user=user,
        in_stock_count=in_stock_count,
        issued_count=issued_count,
        consumed_count=consumed_count,
        firefighters_count=firefighters_count,
        notifications_danger=notifications_danger,
        recent_activity=recent_activity
    )