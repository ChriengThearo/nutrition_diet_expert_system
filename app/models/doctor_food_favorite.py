from datetime import datetime
from extensions import db


class DoctorFoodFavorite(db.Model):
    __tablename__ = "tbl_doctor_food_favorites"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    fdc_id = db.Column(db.Integer, nullable=False)
    food_name = db.Column(db.String(255), nullable=False)
    food_snapshot = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("doctor_id", "fdc_id", name="uq_doctor_food_favorite"),
    )
