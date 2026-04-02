from typing import List, Optional
from app.models.diet_rule import DietRulesTable
from app.models.goal import GoalsTable
from extensions import db
from datetime import datetime

class DietRuleService:
    @staticmethod
    def get_diet_rule_all() -> List[DietRulesTable]:
        return DietRulesTable.query.order_by(DietRulesTable.rule_name.asc()).all()

    @staticmethod
    def get_diet_rule_by_id(diet_rule_id: int) -> Optional[DietRulesTable]:
        return DietRulesTable.query.get(diet_rule_id)

    @staticmethod
    def create_diet_rule(data: dict) -> DietRulesTable:
        try:
            diet_rule = DietRulesTable(
                rule_name=data["rule_name"],
                description=data.get("description", ""),
                conditions=data.get("conditions", ""),
                is_active=data.get("is_active", True),
            )

            db.session.add(diet_rule)
            db.session.flush()
            
            # Add goals
            if data.get('goals'):
                goals = GoalsTable.query.filter(GoalsTable.id.in_(data['goals'])).all()
                diet_rule.goals.extend(goals)
                for goal in goals:
                    goal.diet_rule_id = diet_rule.id
            
            db.session.commit()
            return diet_rule
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def update_diet_rule(diet_rule: DietRulesTable, data: dict) -> DietRulesTable:
        try:
            diet_rule.rule_name = data.get('rule_name', diet_rule.rule_name)
            diet_rule.description = data.get('description', diet_rule.description)
            diet_rule.conditions = data.get('conditions', diet_rule.conditions)
            if 'is_active' in data:
                diet_rule.is_active = data.get('is_active')
            diet_rule.updated_at = datetime.utcnow()
            
            # Update goals
            goals = []
            diet_rule.goals.clear()
            if data.get('goals'):
                goals = GoalsTable.query.filter(GoalsTable.id.in_(data['goals'])).all()
                diet_rule.goals.extend(goals)
                new_goal_ids = {goal.id for goal in goals}
            else:
                new_goal_ids = set()

            if diet_rule.id:
                previous_goal_ids = {
                    goal.id
                    for goal in GoalsTable.query.filter(
                        GoalsTable.diet_rule_id == diet_rule.id
                    ).all()
                }
                removed_ids = previous_goal_ids - new_goal_ids
                if removed_ids:
                    GoalsTable.query.filter(
                        GoalsTable.id.in_(list(removed_ids)),
                        GoalsTable.diet_rule_id == diet_rule.id,
                    ).update({"diet_rule_id": None}, synchronize_session=False)

            for goal in goals:
                goal.diet_rule_id = diet_rule.id
            
            db.session.commit()
            return diet_rule
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def delete_diet_rule(diet_rule: DietRulesTable) -> None:
        GoalsTable.query.filter(
            GoalsTable.diet_rule_id == diet_rule.id
        ).update({"diet_rule_id": None}, synchronize_session=False)
        db.session.delete(diet_rule)
        db.session.commit()
