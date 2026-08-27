from datetime import datetime
from extensions import db


class Consultation(db.Model):
    __tablename__ = "tbl_consultations"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="completed", nullable=False)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    doctor = db.relationship("UserTable", foreign_keys=[doctor_id])
    patient = db.relationship("UserTable", foreign_keys=[patient_id])

    def __repr__(self) -> str:
        return f"<Consultation {self.id} doctor={self.doctor_id} patient={self.patient_id}>"
