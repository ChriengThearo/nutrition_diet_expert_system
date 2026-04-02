from datetime import datetime
from extensions import db
from app.models.associations import tbl_user_goals, tbl_goal_diet_rules


class GoalsTable(db.Model):
    __tablename__ = "tbl_goals"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    target_value = db.Column(db.Float)  # e.g., weight loss in kg
    diet_rule_id = db.Column(db.Integer, db.ForeignKey("tbl_diet_rules.id"))

    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    users = db.relationship(
        "UserTable", secondary=tbl_user_goals, back_populates="goals"
    )
    diet_rules = db.relationship(
        "DietRulesTable", secondary=tbl_goal_diet_rules, back_populates="goals"
    )
    diet_rule = db.relationship("DietRulesTable", back_populates="goals_by_rule")

    def __repr__(self) -> str:
        return f"<Goal {self.name}>"
