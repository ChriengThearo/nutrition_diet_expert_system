from datetime import datetime
from extensions import db


class DoctorPatient(db.Model):
    __tablename__ = "tbl_doctor_patients"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    doctor = db.relationship("UserTable", foreign_keys=[doctor_id])
    patient = db.relationship("UserTable", foreign_keys=[patient_id])

    __table_args__ = (
        db.UniqueConstraint("doctor_id", "patient_id", name="uq_doctor_patient"),
    )

    def __repr__(self) -> str:
        return f"<DoctorPatient doctor={self.doctor_id} patient={self.patient_id}>"
