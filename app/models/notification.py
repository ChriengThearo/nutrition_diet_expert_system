from datetime import datetime
from extensions import db


class Notification(db.Model):
    __tablename__ = "tbl_notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    recipient = db.relationship("UserTable", foreign_keys=[recipient_id])

    def __repr__(self) -> str:
        return f"<Notification {self.id} recipient={self.recipient_id}>"
