from models.user_model import db


class Firefighter(db.Model):
    __tablename__ = "firefighters"

    ROLES = {
        "kierownik_gbr":    "Kierownik GBR",
        "strazak":          "Strażak",
        "ratownik_medyczny": "Ratownik Medyczny (Pielęgniarz)",
    }

    firefighter_id = db.Column(db.Integer, primary_key=True)
    first_name     = db.Column(db.String(100), nullable=False)
    last_name      = db.Column(db.String(100), nullable=False)
    role           = db.Column(db.String(30), nullable=False, default="strazak")
    nfc_username   = db.Column(db.String(200), nullable=True)
    nfc_hash       = db.Column(db.String(300), unique=True, nullable=True)
    height_cm      = db.Column(db.SmallInteger, nullable=True)
    chest_cm       = db.Column(db.SmallInteger, nullable=True)
    waist_cm       = db.Column(db.SmallInteger, nullable=True)
    hat_size       = db.Column(db.Numeric(4, 1), nullable=True)
    shirt_size     = db.Column(db.String(10), nullable=True)
    shoe_size      = db.Column(db.Numeric(4, 1), nullable=True)
    is_active      = db.Column(db.Boolean, nullable=False, default=True)
    created_at     = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at     = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    items = db.relationship("Item", backref="firefighter", lazy="dynamic")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def role_label(self):
        return self.ROLES.get(self.role, self.role)

    @property
    def has_nfc(self):
        return bool(self.nfc_hash)

    @property
    def measurements_complete(self):
        return all([self.height_cm, self.chest_cm, self.waist_cm,
                    self.hat_size, self.shirt_size, self.shoe_size])

    def to_dict(self):
        return {
            "firefighter_id": self.firefighter_id,
            "first_name":     self.first_name,
            "last_name":      self.last_name,
            "full_name":      self.full_name,
            "role":           self.role,
            "role_label":     self.role_label,
            "has_nfc":        self.has_nfc,
            "nfc_username":   self.nfc_username,
            "is_active":      self.is_active,
        }