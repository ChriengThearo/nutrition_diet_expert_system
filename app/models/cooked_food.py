from datetime import datetime
from extensions import db


class CookedFoodsTable(db.Model):
    __tablename__ = "tbl_cooked_foods"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    photo = db.Column(db.String(255))
    is_gevan = db.Column(db.Boolean, default=False, nullable=False)
    food_type = db.Column(db.String(20), default="cooked", nullable=False)
    cooking_method = db.Column(db.String(80))
    description = db.Column(db.String(255))
    calories = db.Column(db.Float)
    protein = db.Column(db.Float)
    carbs = db.Column(db.Float)
    fat = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CookedFood {self.name}>"
