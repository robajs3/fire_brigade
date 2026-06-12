from models.user_model import db, User
from sqlalchemy.exc import SQLAlchemyError


def _normalize_nfc(value):
    if not value:
        return None
    return value.strip().lower().replace(":", "").replace("-", "").replace(" ", "") or None
class UserService:

    @staticmethod
    def get_user_by_cas_username(cas_username):
        return User.query.filter_by(cas_username=cas_username).first()

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def get_user_by_nfc_hash(nfc_hash):
        if not nfc_hash:
            return None
        normalized = _normalize_nfc(nfc_hash)
        return User.query.filter_by(nfc_hash=normalized).first()

    @staticmethod
    def get_all_active_users():
        return User.query.filter_by(is_active=True).all()

    @staticmethod
    def get_all_users():
        return User.query.order_by(User.is_active.desc(), User.full_name).all()

    @staticmethod
    def create_user(cas_username, full_name=None, role="viewer"):
        try:
            user = User(
                cas_username=cas_username,
                full_name=full_name,
                role=role,
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            return user
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def update_user(user_id, full_name=None, role=None, is_active=None, nfc_hash=None):
        user = UserService.get_user_by_id(user_id)
        if not user:
            return None
        try:
            if full_name is not None:
                user.full_name = full_name
            if role is not None:
                user.role = role
            if is_active is not None:
                user.is_active = is_active
            if nfc_hash is not None:
                user.nfc_hash = _normalize_nfc(nfc_hash)
            db.session.commit()
            return user
        except SQLAlchemyError:
            db.session.rollback()
            return None

    @staticmethod
    def deactivate_user(user_id):
        user = UserService.get_user_by_id(user_id)
        if not user:
            return False
        try:
            user.is_active = False
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            return False

    @staticmethod
    def delete_user(user_id):
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            db.session.delete(user)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def ensure_user_exists(cas_username, full_name=None):
        user = UserService.get_user_by_cas_username(cas_username)
        if user:
            if full_name and user.full_name != full_name:
                try:
                    user.full_name = full_name
                    db.session.commit()
                except SQLAlchemyError:
                    db.session.rollback()
            return user
        return UserService.create_user(
            cas_username=cas_username,
            full_name=full_name,
            role="viewer"
        )