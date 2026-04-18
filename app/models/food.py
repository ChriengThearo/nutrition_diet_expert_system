from datetime import datetime
from extensions import db


class FoodsTable(db.Model):
    __tablename__ = "tbl_foods"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    photo = db.Column(db.String(255))
    is_gevan = db.Column(db.Boolean, default=False, nullable=False)
    food_type = db.Column(db.String(20), default="general", nullable=False)
    description = db.Column(db.String(255))
    calories = db.Column(db.Float)  # Simplified column name
    protein = db.Column(db.Float)  # Simplified column name
    carbs = db.Column(db.Float)  # Simplified column name
    fat = db.Column(db.Float)  # Simplified column name

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    rule_food_maps = db.relationship("RuleFoodMapTable", back_populates="food")

    def __repr__(self) -> str:
        return f"<Food {self.name}>"
