from sqlalchemy.exc import SQLAlchemyError
from models.user_model import db
from models.firefighter_model import Firefighter
from models.item_model import Item, IssuanceLog


class FirefighterService:

    @staticmethod
    def get_all_active():
        return Firefighter.query.filter_by(is_active=True).all()

    @staticmethod
    def get_by_id(firefighter_id):
        return Firefighter.query.get(firefighter_id)

    @staticmethod
    def get_by_nfc_hash(nfc_hash):
        if not nfc_hash:
            return None
        return Firefighter.query.filter_by(nfc_hash=nfc_hash).first()

    @staticmethod
    def create(first_name, last_name,
               nfc_username=None, nfc_hash=None,
               height_cm=None, chest_cm=None, waist_cm=None,
               hat_size=None, shirt_size=None, shoe_size=None):
        try:
            nfc_hash     = nfc_hash.strip()     or None if nfc_hash     else None
            nfc_username = nfc_username.strip() or None if nfc_username else None

            firefighter = Firefighter(
                first_name=first_name,
                last_name=last_name,
                nfc_username=nfc_username,
                nfc_hash=nfc_hash,
                height_cm=height_cm or None,
                chest_cm=chest_cm or None,
                waist_cm=waist_cm or None,
                hat_size=hat_size or None,
                shirt_size=shirt_size or None,
                shoe_size=shoe_size or None,
                is_active=True
            )
            db.session.add(firefighter)
            db.session.commit()
            return firefighter
        except SQLAlchemyError as e:
            db.session.rollback()
            print("BŁĄD DODAWANIA:", e)
            return None

    @staticmethod
    def update(firefighter_id, **kwargs):
        firefighter = FirefighterService.get_by_id(firefighter_id)
        if not firefighter:
            return None
        allowed_fields = {
            "first_name", "last_name",
            "nfc_username", "nfc_hash",
            "is_active",
            "height_cm", "chest_cm", "waist_cm",
            "hat_size", "shirt_size", "shoe_size"
        }
        try:
            for key, value in kwargs.items():
                if key in allowed_fields:
                    if key in ("nfc_hash", "nfc_username") and isinstance(value, str):
                        value = value.strip() or None
                    setattr(firefighter, key, value)
            db.session.commit()
            return firefighter
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def attach_nfc(firefighter_id, nfc_username, nfc_hash):
        firefighter = FirefighterService.get_by_id(firefighter_id)
        if not firefighter:
            return None
        existing = FirefighterService.get_by_nfc_hash(nfc_hash)
        if existing and existing.firefighter_id != firefighter_id:
            return None
        try:
            firefighter.nfc_username = nfc_username.strip() or None if nfc_username else None
            firefighter.nfc_hash     = nfc_hash.strip()     or None if nfc_hash     else None
            db.session.commit()
            return firefighter
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def deactivate(firefighter_id):
        firefighter = FirefighterService.get_by_id(firefighter_id)
        if not firefighter:
            return False
        try:
            firefighter.is_active = False
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def get_issued_items(firefighter_id):
        return Item.query.filter_by(
            firefighter_id=firefighter_id,
            is_consumed=False
        ).all()

    @staticmethod
    def delete(firefighter_id):
        try:
            ff = Firefighter.query.get(firefighter_id)
            if not ff:
                return False

            # Blokuj tylko gdy strażak ma aktywnie wydane przedmioty
            has_issued = ff.items.filter(
                Item.is_consumed == False,
                Item.firefighter_id == firefighter_id
            ).count() > 0

            if has_issued:
                return False

            # Wyzeruj firefighter_id w logach przed usunięciem
            IssuanceLog.query.filter_by(firefighter_id=firefighter_id).update(
                {"firefighter_id": None}
            )

            db.session.delete(ff)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print("BŁĄD USUWANIA:", e)
            return False