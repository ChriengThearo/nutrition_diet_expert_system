from datetime import datetime
from extensions import db


class UserResultsTable(db.Model):
    __tablename__ = "tbl_user_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("tbl_users.id"), nullable=False)
    bmi = db.Column(db.Float)  # BMI value
    status = db.Column(db.String(20), default="pending")  # pending, completed
    result_data = db.Column(db.Text)  # JSON payload for plans or diagnoses
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("UserTable", backref="user_results")

    def __repr__(self) -> str:
        return f"<UserResult {self.id} for User {self.user_id}>"
