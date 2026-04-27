from models.user_model import db, User
from sqlalchemy.exc import SQLAlchemyError


class UserService:

    # ---------------------------------------------------------
    # GETTERS
    # ---------------------------------------------------------

    @staticmethod
    def get_user_by_cas_username(cas_username):
        return User.query.filter_by(cas_username=cas_username).first()

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def get_all_active_users():
        return User.query.filter_by(is_active=True).all()

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    @staticmethod
    def update_user(user_id, full_name=None, role=None, is_active=None):
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

            db.session.commit()
            return user
        except SQLAlchemyError:
            db.session.rollback()
            return None

    # ---------------------------------------------------------
    # DEACTIVATE
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # ENSURE USER EXISTS (CAS)
    # ---------------------------------------------------------

    @staticmethod
    def ensure_user_exists(cas_username, full_name=None):
        """
        Używane przy logowaniu CAS:
        - jeśli użytkownik istnieje → zwraca go
        - jeśli nie istnieje → tworzy
        - jeśli istnieje i podano full_name → aktualizuje
        """
        user = UserService.get_user_by_cas_username(cas_username)

        if user:
            # Aktualizacja full_name jeśli podano
            if full_name and user.full_name != full_name:
                try:
                    user.full_name = full_name
                    db.session.commit()
                except SQLAlchemyError:
                    db.session.rollback()
            return user

        # Tworzymy nowego użytkownika
        return UserService.create_user(
            cas_username=cas_username,
            full_name=full_name,
            role="viewer"
        )
