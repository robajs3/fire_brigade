from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from models.user_model import db
from models.item_model import Item
from models.firefighter_model import Firefighter


class NotificationService:

    # ---------------------------------------------------------
    # GET NOTIFICATIONS
    # ---------------------------------------------------------

    @staticmethod
    def get_notifications():
        today = date.today()
        limit_date = today + timedelta(days=60)

        # Pobieramy tylko przedmioty wydane i z okresem ważności
        items = Item.query.filter(
            Item.is_consumed.is_(False),
            Item.issue_date.is_not(None),
            Item.usage_period_months.is_not(None)
        ).all()

        notifications = []

        for item in items:
            # Obliczamy expiry_date
            expiry_date = item.issue_date + relativedelta(months=item.usage_period_months)

            if expiry_date <= limit_date:
                days_remaining = (expiry_date - today).days

                # Ustalenie severity
                if days_remaining <= 0:
                    severity = "danger"
                elif days_remaining <= 14:
                    severity = "warning"
                else:
                    severity = "info"

                # Pobranie strażaka (może być NULL)
                firefighter = None
                if item.firefighter_id:
                    firefighter = Firefighter.query.get(item.firefighter_id)

                notifications.append({
                    "item_id": item.item_id,
                    "item_name": item.name,
                    "firefighter_name": firefighter.full_name if firefighter else None,
                    "issue_date": item.issue_date.isoformat(),
                    "expiry_date": expiry_date.isoformat(),
                    "days_remaining": days_remaining,
                    "severity": severity,
                })

        # Sortowanie:
        # 1. danger → warning → info
        # 2. w ramach grupy po days_remaining rosnąco
        severity_order = {"danger": 0, "warning": 1, "info": 2}

        notifications.sort(
            key=lambda n: (severity_order[n["severity"]], n["days_remaining"])
        )

        return notifications

    # ---------------------------------------------------------
    # GET NOTIFICATIONS COUNT
    # ---------------------------------------------------------

    @staticmethod
    def get_notifications_count():
        notifications = NotificationService.get_notifications()

        counts = {
            "danger": 0,
            "warning": 0,
            "info": 0,
            "total": 0
        }

        for n in notifications:
            counts[n["severity"]] += 1

        counts["total"] = len(notifications)
        return counts
