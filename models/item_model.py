from datetime import date
from models.user_model import db


class ItemCatalog(db.Model):
    __tablename__ = "item_catalog"

    catalog_id          = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(200), nullable=False, unique=True)
    unit_of_measure     = db.Column(db.String(50), nullable=False, default="szt")
    usage_period_months = db.Column(db.Integer, nullable=True)
    default_notes       = db.Column(db.Text, nullable=True)
    is_active           = db.Column(db.Boolean, nullable=False, default=True)
    created_at          = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    items = db.relationship("Item", backref="catalog_item", lazy="dynamic")

    def __repr__(self):
        return f"<ItemCatalog {self.name}>"

    def to_dict(self):
        return {
            "catalog_id":          self.catalog_id,
            "name":                self.name,
            "unit_of_measure":     self.unit_of_measure,
            "usage_period_months": self.usage_period_months,
            "default_notes":       self.default_notes,
            "is_active":           self.is_active,
        }


class Item(db.Model):
    __tablename__ = "items"

    item_id              = db.Column(db.Integer, primary_key=True)
    catalog_id           = db.Column(db.Integer, db.ForeignKey("item_catalog.catalog_id"), nullable=True)
    name                 = db.Column(db.String(200), nullable=False)
    unit_of_measure      = db.Column(db.String(50), nullable=False, default="szt")
    usage_period_months  = db.Column(db.Integer, nullable=True)
    firefighter_id       = db.Column(db.Integer, db.ForeignKey("firefighters.firefighter_id"), nullable=True)
    issue_date           = db.Column(db.Date, nullable=True)
    clothing_card_number = db.Column(db.String(100), nullable=True)
    notes                = db.Column(db.Text, nullable=True)
    is_consumed          = db.Column(db.Boolean, nullable=False, default=False)
    created_at           = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at           = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    @property
    def is_issued(self):
        return bool(self.firefighter_id and self.issue_date)

    @property
    def is_in_stock(self):
        return not self.is_issued and not self.is_consumed

    @property
    def expiry_date(self):
        if self.issue_date and self.usage_period_months:
            from dateutil.relativedelta import relativedelta
            return self.issue_date + relativedelta(months=self.usage_period_months)
        return None

    @property
    def days_until_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - date.today()).days
        return None

    @property
    def status_label(self):
        if self.is_consumed:
            return "Zużyty"
        if self.is_issued:
            return "Wydany"
        return "W magazynie"

    def to_dict(self):
        return {
            "item_id":              self.item_id,
            "catalog_id":           self.catalog_id,
            "name":                 self.name,
            "unit_of_measure":      self.unit_of_measure,
            "usage_period_months":  self.usage_period_months,
            "firefighter_id":       self.firefighter_id,
            "issue_date":           self.issue_date.isoformat() if self.issue_date else None,
            "clothing_card_number": self.clothing_card_number,
            "notes":                self.notes,
            "is_consumed":          self.is_consumed,
            "status_label":         self.status_label,
        }


class IssuanceLog(db.Model):
    __tablename__ = "issuance_log"

    log_id         = db.Column(db.Integer, primary_key=True)
    item_id        = db.Column(db.Integer, db.ForeignKey("items.item_id"), nullable=False)
    firefighter_id = db.Column(db.Integer, db.ForeignKey("firefighters.firefighter_id"), nullable=True)
    action         = db.Column(db.String(20), nullable=False)
    performed_by   = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    nfc_scan       = db.Column(db.Boolean, default=False)
    performed_at   = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    notes          = db.Column(db.Text, nullable=True)
