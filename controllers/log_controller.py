from flask import Blueprint, render_template, session, redirect, url_for, request
from functools import wraps
from services.user_service import UserService
from models.user_model import db, User
from models.item_model import IssuanceLog, Item
from models.firefighter_model import Firefighter

log_bp = Blueprint("log_controller", __name__, url_prefix="/Sp")


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


@log_bp.route("/logs")
@role_required(["manager", "admin"])
def logs_list():
    action_filter      = request.args.get("action", "all")
    nfc_filter         = request.args.get("nfc", "all")
    firefighter_filter = request.args.get("firefighter_id", "")
    limit              = int(request.args.get("limit", 100))

    query = (
        db.session.query(IssuanceLog, Item, User)
        .join(Item, IssuanceLog.item_id == Item.item_id)
        .outerjoin(User, IssuanceLog.performed_by == User.user_id)
    )

    if action_filter != "all":
        query = query.filter(IssuanceLog.action == action_filter)

    if nfc_filter == "nfc":
        query = query.filter(IssuanceLog.nfc_scan == True)
    elif nfc_filter == "manual":
        query = query.filter(IssuanceLog.nfc_scan == False)

    if firefighter_filter:
        # Filtruj po strażaku – szukaj w logach gdzie firefighter_id pasuje
        # lub w poprzednim logu issued dla tego przedmiotu
        query = query.filter(IssuanceLog.firefighter_id == int(firefighter_filter))

    raw_logs = query.order_by(IssuanceLog.performed_at.desc()).limit(limit).all()

    # Dla każdego logu znajdź strażaka
    # Jeśli log ma firefighter_id → użyj go
    # Jeśli nie → znajdź z ostatniego logu 'issued' dla tego przedmiotu
    logs = []
    for log, item, performed_by_user in raw_logs:
        firefighter = None

        if log.firefighter_id:
            firefighter = Firefighter.query.get(log.firefighter_id)
        else:
            # Szukaj w poprzednim logu 'issued' dla tego przedmiotu
            issued_log = (
                IssuanceLog.query
                .filter_by(item_id=log.item_id, action="issued")
                .filter(IssuanceLog.performed_at <= log.performed_at)
                .filter(IssuanceLog.firefighter_id.isnot(None))
                .order_by(IssuanceLog.performed_at.desc())
                .first()
            )
            if issued_log:
                firefighter = Firefighter.query.get(issued_log.firefighter_id)

        logs.append((log, item, firefighter, performed_by_user))

    firefighters = Firefighter.query.filter_by(is_active=True).order_by(Firefighter.last_name).all()

    return render_template(
        "logs/list.html",
        logs=logs,
        firefighters=firefighters,
        action_filter=action_filter,
        nfc_filter=nfc_filter,
        firefighter_filter=firefighter_filter,
        limit=limit,
    )