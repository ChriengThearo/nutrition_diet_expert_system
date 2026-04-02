from datetime import datetime
from extensions import db
from app.models.associations import tbl_goal_diet_rules


class DietRulesTable(db.Model):
    __tablename__ = "tbl_diet_rules"

    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    conditions = db.Column(db.Text)  # JSON or text for rule conditions

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    goals = db.relationship(
        "GoalsTable", secondary=tbl_goal_diet_rules, back_populates="diet_rules"
    )
    goals_by_rule = db.relationship("GoalsTable", back_populates="diet_rule")
    rule_food_maps = db.relationship("RuleFoodMapTable", back_populates="diet_rule")

    # Add property for backward compatibility
    @property
    def name(self):
        return self.rule_name

    @name.setter
    def name(self, value):
        self.rule_name = value

    def __repr__(self) -> str:
        return f"<DietRule {self.rule_name}>"
