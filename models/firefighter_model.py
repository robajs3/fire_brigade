from sqlalchemy.sql import func
from models.user_model import db


class Firefighter(db.Model):
    __tablename__ = "firefighters"

    firefighter_id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)

    nfc_username = db.Column(db.String(200))
    nfc_hash = db.Column(db.String(300), unique=True)

    height_cm = db.Column(db.SmallInteger)
    chest_cm = db.Column(db.SmallInteger)
    waist_cm = db.Column(db.SmallInteger)
    hat_size = db.Column(db.Numeric(4, 1))
    shirt_size = db.Column(db.String(10))
    shoe_size = db.Column(db.Numeric(4, 1))

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relacja one-to-many z Item
    items = db.relationship(
        "Item",
        backref="firefighter",
        lazy="dynamic"
    )

    # --- PROPERTIES ---

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def has_nfc(self):
        return bool(self.nfc_hash)

    @property
    def measurements_complete(self):
        return all([
            self.height_cm,
            self.chest_cm,
            self.waist_cm,
            self.hat_size,
            self.shirt_size,
            self.shoe_size
        ])

    # --- SERIALIZACJA ---

    def to_dict(self):
        return {
            "firefighter_id": self.firefighter_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "nfc_username": self.nfc_username,
            "nfc_hash": self.nfc_hash,
            "height_cm": self.height_cm,
            "chest_cm": self.chest_cm,
            "waist_cm": self.waist_cm,
            "hat_size": float(self.hat_size) if self.hat_size is not None else None,
            "shirt_size": self.shirt_size,
            "shoe_size": float(self.shoe_size) if self.shoe_size is not None else None,
            "is_active": self.is_active,
            "has_nfc": self.has_nfc,
            "measurements_complete": self.measurements_complete,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    # --- REPR ---

    def __repr__(self):
        return f"<Firefighter {self.firefighter_id} {self.full_name}>"
