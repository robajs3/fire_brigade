from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from models.user_model import db
from models.item_model import Item, RoleRequiredItem
from models.firefighter_model import Firefighter


class NotificationService:

    # ---------------------------------------------------------
    # 1. Zbliżające się wymiany
    # ---------------------------------------------------------
    @staticmethod
    def get_expiry_notifications():
        today      = date.today()
        limit_date = today + timedelta(days=60)

        items = Item.query.filter(
            Item.is_consumed.is_(False),
            Item.issue_date.is_not(None),
            Item.usage_period_months.is_not(None)
        ).all()

        notifications = []
        for item in items:
            expiry_date = item.issue_date + relativedelta(months=item.usage_period_months)
            if expiry_date <= limit_date:
                days_remaining = (expiry_date - today).days
                if days_remaining <= 0:
                    severity = "danger"
                elif days_remaining <= 14:
                    severity = "warning"
                else:
                    severity = "info"

                ff = Firefighter.query.get(item.firefighter_id) if item.firefighter_id else None
                notifications.append({
                    "type":             "expiry",
                    "item_id":          item.item_id,
                    "item_name":        item.name,
                    "firefighter_name": ff.full_name if ff else "—",
                    "firefighter_id":   ff.firefighter_id if ff else None,
                    "issue_date":       item.issue_date.isoformat(),
                    "expiry_date":      expiry_date.isoformat(),
                    "days_remaining":   days_remaining,
                    "severity":         severity,
                    "message":          f"Przedmiot '{item.name}' wymaga wymiany za {days_remaining} dni"
                                        if days_remaining > 0
                                        else f"Przedmiot '{item.name}' jest przeterminowany",
                })

        severity_order = {"danger": 0, "warning": 1, "info": 2}
        notifications.sort(key=lambda n: (severity_order[n["severity"]], n["days_remaining"]))
        return notifications

    # ---------------------------------------------------------
    # 2. Brak NFC
    # ---------------------------------------------------------
    @staticmethod
    def get_no_nfc_notifications():
        firefighters = Firefighter.query.filter_by(is_active=True).all()
        notifications = []
        for ff in firefighters:
            if not ff.has_nfc:
                notifications.append({
                    "type":           "no_nfc",
                    "firefighter_id": ff.firefighter_id,
                    "firefighter_name": ff.full_name,
                    "role_label":     ff.role_label,
                    "severity":       "warning",
                    "message":        f"{ff.full_name} ({ff.role_label}) nie ma przypisanej karty NFC",
                })
        return notifications

    # ---------------------------------------------------------
    # 3. Brak wymaganego wyposażenia (tylko strażacy z NFC)
    # ---------------------------------------------------------
    @staticmethod
    def get_missing_equipment_notifications():
        notifications = []

        # Tylko strażacy z NFC
        firefighters = Firefighter.query.filter(
            Firefighter.is_active.is_(True),
            Firefighter.nfc_hash.is_not(None)
        ).all()

        for ff in firefighters:
            # Wymagane pozycje dla tej roli
            required = RoleRequiredItem.query.filter_by(
                role=ff.role,
                is_required=True
            ).all()

            # Co strażak ma aktualnie wydane (nie zużyte)
            issued_catalog_ids = db.session.query(Item.catalog_id).filter(
                Item.firefighter_id == ff.firefighter_id,
                Item.is_consumed.is_(False),
                Item.catalog_id.is_not(None)
            ).all()
            issued_catalog_ids = {row[0] for row in issued_catalog_ids}

            for req in required:
                if req.catalog_id not in issued_catalog_ids:
                    notifications.append({
                        "type":             "missing_equipment",
                        "firefighter_id":   ff.firefighter_id,
                        "firefighter_name": ff.full_name,
                        "role_label":       ff.role_label,
                        "catalog_id":       req.catalog_id,
                        "item_name":        req.catalog_item.name,
                        "severity":         "danger",
                        "message":          f"{ff.full_name} nie ma wydanego: {req.catalog_item.name}",
                    })

        return notifications

    # ---------------------------------------------------------
    # Wszystkie powiadomienia
    # ---------------------------------------------------------
    @staticmethod
    def get_notifications():
        all_notifs = (
            NotificationService.get_missing_equipment_notifications() +
            NotificationService.get_no_nfc_notifications() +
            NotificationService.get_expiry_notifications()
        )
        return all_notifs

    @staticmethod
    def get_notifications_count():
        notifs = NotificationService.get_notifications()
        counts = {"danger": 0, "warning": 0, "info": 0, "total": 0}
        for n in notifs:
            counts[n["severity"]] += 1
        counts["total"] = len(notifs)
        return counts