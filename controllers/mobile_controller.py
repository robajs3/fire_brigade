from flask import Blueprint, render_template, session, redirect, url_for, request, flash, jsonify
from functools import wraps
from datetime import date

from services.user_service import UserService
from services.item_service import ItemService
from services.firefighter_service import FirefighterService
from services.catalog_service import CatalogService
from models.item_model import RoleRequiredItem, Item

mobile_bp = Blueprint("mobile_controller", __name__, url_prefix="/zsr/mobile")


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


@mobile_bp.route("/scan")
@role_required()
def mobile_scan():
    session.pop("last_nfc_scan", None)
    firefighters = FirefighterService.get_all_active()
    return render_template("mobile/scan.html", firefighters=firefighters)


@mobile_bp.route("/firefighters")
@role_required()
def mobile_firefighters():
    firefighters = FirefighterService.get_all_active()
    return render_template("mobile/firefighters.html", firefighters=firefighters)


@mobile_bp.route("/notifications")
@role_required()
def mobile_notifications():
    from services.notification_service import NotificationService
    notifications = NotificationService.get_notifications()
    counts        = NotificationService.get_notifications_count()
    return render_template("mobile/notifications.html",
                           notifications=notifications,
                           counts=counts)


@mobile_bp.route("/logs")
@role_required(["manager", "admin"])
def mobile_logs():
    from models.user_model import db, User
    from models.item_model import IssuanceLog, Item as ItemModel
    from models.firefighter_model import Firefighter

    action_filter      = request.args.get("action", "all")
    nfc_filter         = request.args.get("nfc", "all")
    firefighter_filter = request.args.get("firefighter_id", "")

    query = (
        db.session.query(IssuanceLog, ItemModel, User)
        .join(ItemModel, IssuanceLog.item_id == ItemModel.item_id)
        .outerjoin(User, IssuanceLog.performed_by == User.user_id)
    )

    if action_filter != "all":
        query = query.filter(IssuanceLog.action == action_filter)
    if nfc_filter == "nfc":
        query = query.filter(IssuanceLog.nfc_scan == True)
    elif nfc_filter == "manual":
        query = query.filter(IssuanceLog.nfc_scan == False)
    if firefighter_filter:
        query = query.filter(IssuanceLog.firefighter_id == int(firefighter_filter))

    raw_logs = query.order_by(IssuanceLog.performed_at.desc()).limit(200).all()

    logs = []
    for log, item, performed_by_user in raw_logs:
        firefighter = None
        if log.firefighter_id:
            firefighter = Firefighter.query.get(log.firefighter_id)
        else:
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

    firefighters = FirefighterService.get_all_active()

    return render_template(
        "mobile/logs.html",
        logs=logs,
        firefighters=firefighters,
        action_filter=action_filter,
        nfc_filter=nfc_filter,
        firefighter_filter=firefighter_filter,
    )


@mobile_bp.route("/firefighter/<int:firefighter_id>")
@role_required()
def mobile_firefighter(firefighter_id):
    firefighter = FirefighterService.get_by_id(firefighter_id)
    if not firefighter:
        flash("Nie znaleziono strażaka.", "danger")
        return redirect(url_for("mobile_controller.mobile_scan"))

    nfc_scan     = session.get("last_nfc_scan", False)
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

    catalog       = CatalogService.get_all_active()
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


@mobile_bp.route("/api/firefighter-by-nfc/<nfc_hash>")
@role_required()
def api_firefighter_by_nfc(nfc_hash):
    ff = FirefighterService.get_by_nfc_hash(nfc_hash)
    if not ff:
        return jsonify({"error": "Nie znaleziono"}), 404

    session["last_nfc_scan"] = True
    session.modified = True

    return jsonify({
        "id":        ff.firefighter_id,
        "full_name": ff.full_name,
        "role":      ff.role_label
    })
    
# ─────────────────────────────────────────────
#  MAGAZYN MOBILNY  –  dodaj do mobile_controller.py
# ─────────────────────────────────────────────

from collections import defaultdict


def _warehouse_summary(entries):
    """Zwraca słownik z liczbami do kafelków podsumowania."""
    total     = len(entries)
    available = sum(1 for e in entries if e.qty_free > 0
                    and e.qty_free > e.low_stock_threshold)
    low       = sum(1 for e in entries if 0 < e.qty_free <= e.low_stock_threshold)
    return {"total": total, "available": available, "low": low}


@mobile_bp.route("/warehouse")
@role_required()
def mobile_warehouse():
    from models.item_model import Item

    q               = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "all")
    stock_filter    = request.args.get("stock", "all")

    # Pobierz aktywne pozycje katalogu
    catalog_items = CatalogService.get_all_active()

    # Pobierz surowe przedmioty (nie skonsumowane)
    items_query = Item.query.filter_by(is_consumed=False)
    all_items   = items_query.all()

    # Zgrupuj po catalog_id
    free_counts   = defaultdict(int)
    issued_counts = defaultdict(int)
    for it in all_items:
        if it.catalog_id:
            if it.firefighter_id is None:
                free_counts[it.catalog_id]   += 1
            else:
                issued_counts[it.catalog_id] += 1

    # Zbuduj listę wpisów widoku
    LOW_STOCK_DEFAULT = 2   # jeśli CatalogItem nie ma własnego progu

    class WarehouseEntry:
        def __init__(self, catalog_item):
            self.catalog_item      = catalog_item
            self.qty_free          = free_counts.get(catalog_item.catalog_id, 0)
            self.qty_issued        = issued_counts.get(catalog_item.catalog_id, 0)
            self.low_stock_threshold = getattr(
                catalog_item, "low_stock_threshold", LOW_STOCK_DEFAULT
            )

    entries = [WarehouseEntry(c) for c in catalog_items]

    # Filtr tekstowy
    if q:
        entries = [e for e in entries
                   if q.lower() in e.catalog_item.name.lower()]

    # Filtr kategorii
    categories = sorted({
        e.catalog_item.category
        for e in entries
        if getattr(e.catalog_item, "category", None)
    })
    if category_filter != "all":
        entries = [e for e in entries
                   if getattr(e.catalog_item, "category", None) == category_filter]

    # Filtr stanu
    if stock_filter == "ok":
        entries = [e for e in entries
                   if e.qty_free > e.low_stock_threshold]
    elif stock_filter == "low":
        entries = [e for e in entries
                   if 0 < e.qty_free <= e.low_stock_threshold]
    elif stock_filter == "zero":
        entries = [e for e in entries if e.qty_free == 0]

    summary = _warehouse_summary(entries)

    # Rola zalogowanego użytkownika (do szablonu)
    user = UserService.get_user_by_cas_username(session["CAS_USERNAME"])

    return render_template(
        "mobile/warehouse.html",
        items=entries,
        categories=categories,
        q=q,
        category_filter=category_filter,
        stock_filter=stock_filter,
        summary=summary,
        current_user_role=user.role,
    )


@mobile_bp.route("/warehouse/receive", methods=["GET"])
@role_required(["manager", "admin"])
def mobile_warehouse_receive_form():
    catalog              = CatalogService.get_all_active()
    preselected_catalog_id = request.args.get("catalog_id", type=int)
    return render_template(
        "mobile/warehouse_receive.html",
        catalog=catalog,
        preselected_catalog_id=preselected_catalog_id,
        today=date.today().isoformat(),
    )


@mobile_bp.route("/warehouse/receive", methods=["POST"])
@role_required(["manager", "admin"])
def mobile_warehouse_receive():
    catalog_id      = request.form.get("catalog_id", type=int)
    quantity        = request.form.get("quantity", type=int)
    receive_date    = request.form.get("receive_date")
    document_number = request.form.get("document_number", "").strip() or None
    notes           = request.form.get("notes", "").strip() or None

    if not catalog_id or not quantity or quantity < 1:
        flash("Podaj przedmiot i ilość.", "danger")
        return redirect(url_for("mobile_controller.mobile_warehouse_receive_form"))

    catalog_entry = CatalogService.get_by_id(catalog_id)
    if not catalog_entry:
        flash("Nie znaleziono przedmiotu w katalogu.", "danger")
        return redirect(url_for("mobile_controller.mobile_warehouse_receive_form"))

    user = UserService.get_user_by_cas_username(session["CAS_USERNAME"])

    # Utwórz `quantity` nowych rekordów Item
    success = ItemService.receive_items(
        catalog_id=catalog_id,
        quantity=quantity,
        receive_date=receive_date,
        performed_by_user_id=user.user_id,
        document_number=document_number,
        notes=notes,
    )

    if not success:
        flash("Błąd podczas przyjęcia przedmiotów.", "danger")
        return redirect(url_for("mobile_controller.mobile_warehouse_receive_form"))

    return render_template(
        "mobile/warehouse_success.html",
        catalog_entry=catalog_entry,
        quantity=quantity,
        receive_date=receive_date,
        document_number=document_number,
        notes=notes,
    )

@mobile_bp.route("/firefighter/<int:firefighter_id>/assign-nfc", methods=["POST"])
@role_required(["manager", "admin"])
def mobile_assign_nfc(firefighter_id):
    nfc_username = request.form.get("nfc_username") or None
    nfc_hash     = request.form.get("nfc_hash") or None

    if not nfc_hash:
        flash("Brak danych karty NFC.", "danger")
        return redirect(url_for("mobile_controller.mobile_firefighter",
                                firefighter_id=firefighter_id))

    existing = FirefighterService.get_by_nfc_hash(nfc_hash)
    if existing and existing.firefighter_id != firefighter_id:
        flash(f"Ta karta jest już przypisana do: {existing.full_name}.", "danger")
        return redirect(url_for("mobile_controller.mobile_firefighter",
                                firefighter_id=firefighter_id))

    result = FirefighterService.update(
        firefighter_id,
        nfc_username=nfc_username,
        nfc_hash=nfc_hash
    )

    if result:
        flash("Karta NFC została przypisana.", "success")
    else:
        flash("Błąd podczas przypisywania karty NFC.", "danger")

    return redirect(url_for("mobile_controller.mobile_firefighter",
                            firefighter_id=firefighter_id))