from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    cas_username = db.Column(db.String(100), unique=True, nullable=False)
    full_name = db.Column(db.String(200))
    role = db.Column(db.String(20), nullable=False, default="viewer")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # --- REPR ---
    def __repr__(self):
        return f"<User {self.user_id} {self.cas_username} ({self.role})>"

    # --- PROPERTY ---
    @property
    def full_name_or_username(self):
        return self.full_name if self.full_name else self.cas_username

    # --- SERIALIZACJA ---
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "cas_username": self.cas_username,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
