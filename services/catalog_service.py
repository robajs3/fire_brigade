from sqlalchemy.exc import SQLAlchemyError
from models.user_model import db
from models.item_model import ItemCatalog, RoleRequiredItem


class CatalogService:

    @staticmethod
    def get_all_active():
        return ItemCatalog.query.filter_by(is_active=True).order_by(ItemCatalog.name).all()

    @staticmethod
    def get_all():
        return ItemCatalog.query.order_by(ItemCatalog.name).all()

    @staticmethod
    def get_by_id(catalog_id):
        return ItemCatalog.query.get(catalog_id)

    @staticmethod
    def create(name, unit_of_measure="szt", usage_period_months=None, default_notes=None):
        try:
            entry = ItemCatalog(
                name=name,
                unit_of_measure=unit_of_measure,
                usage_period_months=usage_period_months,
                default_notes=default_notes,
                is_active=True
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def update(catalog_id, **kwargs):
        entry = CatalogService.get_by_id(catalog_id)
        if not entry:
            return None

        allowed = {"name", "unit_of_measure", "usage_period_months", "default_notes", "is_active"}

        try:
            for key, value in kwargs.items():
                if key in allowed:
                    setattr(entry, key, value)
            db.session.commit()
            return entry
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def delete(catalog_id):
        try:
            entry = ItemCatalog.query.get(catalog_id)
            if not entry:
                return False
            if entry.items.count() > 0:
                return False
            db.session.delete(entry)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    # ---------------------------------------------------------
    #   OBSŁUGA WYMAGAŃ RÓL (RoleRequiredItem)
    # ---------------------------------------------------------

    @staticmethod
    def set_role_requirements(catalog_id, role_data):
        """
        role_data = [
            {"role": "strazak", "quantity": 1, "is_required": True},
            ...
        ]
        """
        try:
            # usuń stare wymagania
            RoleRequiredItem.query.filter_by(catalog_id=catalog_id).delete()

            # dodaj nowe
            for rd in role_data:
                if rd.get("role"):
                    req = RoleRequiredItem(
                        catalog_id=catalog_id,
                        role=rd["role"],
                        quantity=int(rd.get("quantity", 1)),
                        is_required=rd.get("is_required", True)
                    )
                    db.session.add(req)

            db.session.commit()
            return True

        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def get_role_requirements(catalog_id):
        return RoleRequiredItem.query.filter_by(catalog_id=catalog_id).all()
