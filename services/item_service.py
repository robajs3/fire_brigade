from datetime import date
from sqlalchemy.exc import SQLAlchemyError

from models.user_model import db
from models.item_model import Item, IssuanceLog


class ItemService:

    @staticmethod
    def get_all_in_stock():
        return Item.query.filter(
            Item.firefighter_id.is_(None),
            Item.is_consumed.is_(False)
        ).all()

    @staticmethod
    def get_all_issued():
        return Item.query.filter(
            Item.firefighter_id.is_not(None),
            Item.is_consumed.is_(False)
        ).all()

    @staticmethod
    def get_all_consumed():
        return Item.query.filter_by(is_consumed=True).all()

    @staticmethod
    def get_by_id(item_id):
        return Item.query.get(item_id)

    @staticmethod
    def create(name, unit_of_measure, usage_period_months=None,
               clothing_card_number=None, notes=None, catalog_id=None):
        try:
            item = Item(
                name=name,
                unit_of_measure=unit_of_measure,
                usage_period_months=usage_period_months,
                clothing_card_number=clothing_card_number,
                notes=notes,
                catalog_id=catalog_id,
                is_consumed=False
            )
            db.session.add(item)
            db.session.commit()
            return item
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def create_bulk(name, unit_of_measure, count,
                    usage_period_months=None, clothing_card_number=None,
                    notes=None, catalog_id=None):
        if count < 1 or count > 500:
            return []

        try:
            items = []
            for _ in range(count):
                item = Item(
                    name=name,
                    unit_of_measure=unit_of_measure,
                    usage_period_months=usage_period_months,
                    clothing_card_number=clothing_card_number,
                    notes=notes,
                    catalog_id=catalog_id,
                    is_consumed=False
                )
                db.session.add(item)
                items.append(item)

            db.session.commit()
            return items

        except SQLAlchemyError:
            db.session.rollback()
            return []

    @staticmethod
    def update(item_id, **kwargs):
        item = ItemService.get_by_id(item_id)
        if not item:
            return None

        allowed_fields = {
            "name", "unit_of_measure", "usage_period_months",
            "clothing_card_number", "notes",
            "firefighter_id", "issue_date", "is_consumed"
        }

        try:
            for key, value in kwargs.items():
                if key in allowed_fields:
                    setattr(item, key, value)
            db.session.commit()
            return item
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def issue_item(item_id, firefighter_id, issue_date,
                   performed_by_user_id,
                   clothing_card_number=None, notes=None, nfc_scan=False):

        item = ItemService.get_by_id(item_id)
        if not item or item.is_consumed:
            return None

        if item.catalog_id:
            existing = Item.query.filter_by(
                firefighter_id=firefighter_id,
                catalog_id=item.catalog_id,
                is_consumed=False
            ).first()

            if existing:
                return existing

        try:
            item.firefighter_id = firefighter_id
            item.issue_date = issue_date

            if clothing_card_number:
                item.clothing_card_number = clothing_card_number
            if notes:
                item.notes = notes

            log = IssuanceLog(
                item_id=item_id,
                firefighter_id=firefighter_id,
                action="issued",
                performed_by=performed_by_user_id,
                nfc_scan=nfc_scan,
                notes=notes
            )

            db.session.add(log)
            db.session.commit()
            return item

        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def return_item(item_id, performed_by_user_id, notes=None):
        item = ItemService.get_by_id(item_id)
        if not item or item.is_consumed:
            return None

        try:
            # Zapisz strażaka PRZED wyzerowaniem – żeby log miał info kto oddał
            previous_firefighter_id = item.firefighter_id

            item.firefighter_id = None
            item.issue_date = None

            log = IssuanceLog(
                item_id=item_id,
                firefighter_id=previous_firefighter_id,
                action="returned",
                performed_by=performed_by_user_id,
                notes=notes
            )

            db.session.add(log)
            db.session.commit()
            return item

        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def mark_consumed(item_id, performed_by_user_id, notes=None):
        item = ItemService.get_by_id(item_id)
        if not item:
            return None

        try:
            # Zapisz strażaka PRZED wyzerowaniem – żeby log miał info kto zużył
            previous_firefighter_id = item.firefighter_id

            item.is_consumed = True
            item.firefighter_id = None
            item.issue_date = None

            log = IssuanceLog(
                item_id=item_id,
                firefighter_id=previous_firefighter_id,
                action="consumed",
                performed_by=performed_by_user_id,
                notes=notes
            )

            db.session.add(log)
            db.session.commit()
            return item

        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def get_expiring_soon(days=30):
        result = []
        today = date.today()
        items = Item.query.filter_by(is_consumed=False).all()

        for item in items:
            expiry = item.expiry_date
            if expiry:
                delta = (expiry - today).days
                if 0 <= delta <= days:
                    result.append(item)

        return result

    @staticmethod
    def get_item_log(item_id):
        return IssuanceLog.query.filter_by(item_id=item_id).order_by(
            IssuanceLog.performed_at.desc()
        ).all()

    @staticmethod
    def delete(item_id):
        try:
            item = Item.query.get(item_id)
            if not item:
                return False

            IssuanceLog.query.filter_by(item_id=item_id).delete()
            db.session.delete(item)
            db.session.commit()
            return True

        except Exception:
            db.session.rollback()
            return False