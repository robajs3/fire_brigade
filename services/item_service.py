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
    def check_sap_stock(catalog_id):
        from models.item_model import ItemCatalog
        if not catalog_id:
            return True, None
        catalog = ItemCatalog.query.get(catalog_id)
        if not catalog or not catalog.sap_matnr:
            return True, None
        stock = float(catalog.sap_stock or 0)
        return stock > 0, stock

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
            available, stock = ItemService.check_sap_stock(item.catalog_id)
            if not available:
                print(f"[SAP] Brak stanu dla catalog_id={item.catalog_id}, stan={stock}")
                return None

        try:
            item.firefighter_id = firefighter_id
            item.issue_date     = issue_date
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

            if item.catalog_id:
                from models.item_model import ItemCatalog
                from services.sap_service import SAPService
                catalog = ItemCatalog.query.get(item.catalog_id)
                if catalog and catalog.sap_matnr and catalog.sap_kostl:
                    sap_result = SAPService.post_goods_issue(
                        matnr=catalog.sap_matnr,
                        menge=1.0,
                        meins=catalog.unit_of_measure.upper(),
                        kostl=catalog.sap_kostl,
                        ref_doc=f"SP-{item_id}"
                    )
                    if sap_result["success"]:
                        if catalog.sap_stock is not None:
                            catalog.sap_stock = float(catalog.sap_stock) - 1.0
                            db.session.commit()
                        print(f"[SAP] Dok. {sap_result['mblnr']}")
                    else:
                        print(f"[SAP] Błąd wydania: {sap_result['error']}")

            return item

        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"[DB] Błąd: {e}")
            return None

    @staticmethod
    def return_item(item_id, performed_by_user_id, notes=None):
        item = ItemService.get_by_id(item_id)
        if not item or item.is_consumed:
            return None

        old_firefighter_id = item.firefighter_id

        try:
            item.firefighter_id = None
            item.issue_date     = None

            log = IssuanceLog(
                item_id=item_id,
                firefighter_id=old_firefighter_id,
                action="returned",
                performed_by=performed_by_user_id,
                notes=notes
            )
            db.session.add(log)
            db.session.commit()

            if item.catalog_id:
                from models.item_model import ItemCatalog
                from services.sap_service import SAPService
                catalog = ItemCatalog.query.get(item.catalog_id)
                if catalog and catalog.sap_matnr and catalog.sap_kostl:
                    sap_result = SAPService.post_goods_return(
                        matnr=catalog.sap_matnr,
                        menge=1.0,
                        meins=catalog.unit_of_measure.upper(),
                        kostl=catalog.sap_kostl,
                        ref_doc=f"SP-ZW-{item_id}"
                    )
                    if sap_result["success"]:
                        if catalog.sap_stock is not None:
                            catalog.sap_stock = float(catalog.sap_stock) + 1.0
                            db.session.commit()
                        print(f"[SAP] Zwrot, dok. {sap_result['mblnr']}")
                    else:
                        print(f"[SAP] Błąd zwrotu: {sap_result['error']}")

            return item

        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def mark_consumed(item_id, performed_by_user_id, notes=None):
        item = ItemService.get_by_id(item_id)
        if not item:
            return None

        old_firefighter_id = item.firefighter_id

        try:
            item.is_consumed    = True
            item.firefighter_id = None
            item.issue_date     = None

            log = IssuanceLog(
                item_id=item_id,
                firefighter_id=old_firefighter_id,
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
    def get_grouped_by_catalog():
        from sqlalchemy import func
        from models.item_model import ItemCatalog

        rows = (
            db.session.query(
                Item.catalog_id,
                Item.name,
                Item.unit_of_measure,
                func.min(Item.item_id).label("first_item_id"),
                func.sum(
                    db.case((Item.firefighter_id.is_(None), 1), else_=0)
                ).label("in_stock"),
                func.sum(
                    db.case((Item.firefighter_id.isnot(None), 1), else_=0)
                ).label("issued"),
                func.count(Item.item_id).label("total"),
                ItemCatalog.sap_matnr,
            )
            .outerjoin(ItemCatalog, Item.catalog_id == ItemCatalog.catalog_id)
            .filter(Item.is_consumed.is_(False))
            .group_by(Item.catalog_id, Item.name, Item.unit_of_measure, ItemCatalog.sap_matnr)
            .all()
        )

        return [
            {
                "catalog_id":    row.catalog_id,
                "name":          row.name,
                "unit":          row.unit_of_measure,
                "first_item_id": row.first_item_id,
                "in_stock":      int(row.in_stock),
                "issued":        int(row.issued),
                "total":         int(row.total),
                "sap_matnr":     row.sap_matnr,
            }
            for row in rows
        ]

    @staticmethod
    def get_expiring_soon(days=30):
        result = []
        today  = date.today()
        items  = Item.query.filter_by(is_consumed=False).all()
        for item in items:
            expiry = item.expiry_date
            if expiry and 0 <= (expiry - today).days <= days:
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