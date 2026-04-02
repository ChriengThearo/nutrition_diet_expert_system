from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from flask_login import current_user
from app.models.user import UserTable
from app.models.role import RoleTable
from app.models.goal import GoalsTable
from app.models.diet_rule import DietRulesTable
from app.models.rule_food_map import RuleFoodMapTable
from app.models.user_result import UserResultsTable
from app.models.food import FoodsTable
from extensions import db
import json
import re
import logging

logger = logging.getLogger(__name__)


class DashboardService:
    """Service class for dashboard business logic"""

    @staticmethod
    def get_admin_statistics() -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        try:
            stats = {
                "total_users": UserTable.query.count(),
                "total_doctors": UserTable.query.join(UserTable.roles)
                .filter(RoleTable.name == "doctor")
                .count(),
                "total_patients": UserTable.query.join(UserTable.roles)
                .filter(RoleTable.name == "user")
                .count(),
                "total_goals": GoalsTable.query.count(),
                "total_rules": DietRulesTable.query.count(),
                "total_foods": FoodsTable.query.count(),
                "total_diagnoses": UserResultsTable.query.count(),
                "active_users": UserTable.query.filter_by(is_active=True).count(),
                "recent_registrations": UserTable.query.filter(
                    UserTable.created_at >= datetime.utcnow() - timedelta(days=7)
                ).count(),
                "pending_diagnoses": UserResultsTable.query.filter_by(
                    status="pending"
                ).count(),
                "completed_diagnoses": UserResultsTable.query.filter_by(
                    status="completed"
                ).count(),
            }

            # Add growth metrics
            stats["user_growth"] = DashboardService._calculate_growth("users")
            stats["diagnosis_growth"] = DashboardService._calculate_growth("diagnoses")

            return stats
        except Exception as e:
            logger.error(f"Error getting admin statistics: {e}")
            return {}

    @staticmethod
    def get_doctor_statistics(doctor_id: Optional[int] = None) -> Dict[str, Any]:
        """Get doctor dashboard statistics"""
        try:
            if doctor_id is None and current_user.is_authenticated:
                doctor_id = current_user.id

            # Simplified statistics - in real implementation would filter by doctor's patients
            stats = {
                "total_patients": UserTable.query.count(),
                "consultations_today": DashboardService._get_today_consultations(
                    doctor_id
                ),
                "consultations_week": DashboardService._get_week_consultations(
                    doctor_id
                ),
                "pending_diagnoses": UserResultsTable.query.filter_by(
                    status="pending"
                ).count(),
                "completed_diagnoses": UserResultsTable.query.filter_by(
                    status="completed"
                ).count(),
                "rules_authored": DietRulesTable.query.count(),  # Simplified
                "recent_patients": DashboardService._get_recent_patients(doctor_id),
                "upcoming_appointments": DashboardService._get_upcoming_appointments(
                    doctor_id
                ),
            }

            return stats
        except Exception as e:
            logger.error(f"Error getting doctor statistics: {e}")
            return {}

    @staticmethod
    def get_user_statistics(user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get user dashboard statistics"""
        try:
            if user_id is None and current_user.is_authenticated:
                user_id = current_user.id

            user = UserTable.query.get(user_id)
            if not user:
                return {}

            # Get latest BMI from user results
            latest_result = user.user_results[-1] if user.user_results else None
            user_bmi = latest_result.bmi if latest_result else None

            stats = {
                "user_bmi": user_bmi,
                "bmi_category": (
                    DashboardService._get_bmi_category(user_bmi) if user_bmi else None
                ),
                "active_goals": len(user.goals),
                "total_diagnoses": len(user.user_results),
                "completed_diagnoses": len(
                    [r for r in user.user_results if r.status == "completed"]
                ),
                "upcoming_appointments": DashboardService._get_user_appointments(
                    user_id
                ),
                "health_score": DashboardService._calculate_health_score(user),
                "last_diagnosis": latest_result.created_at if latest_result else None,
                "recommendations_count": DashboardService._get_recommendations_count(
                    user_id
                ),
            }

            return stats
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {}

    @staticmethod
    def save_user_dashboard_submission(
        user_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Persist user dashboard form data and update related tables."""
        user = UserTable.query.get(user_id)
        if not user:
            raise ValueError("User not found")

        personal = payload.get("personal", {}) or {}
        health = payload.get("health", {}) or {}
        goals = payload.get("goals", {}) or {}

        # Update goals based on selected goal
        goal_code = goals.get("goal")
        goal_map = {
            "weight_loss": "Weight Loss",
            "muscle_gain": "Muscle Gain",
            "maintenance": "Weight Maintenance",
            "improve_health": "Improve Health",
            "athletic_performance": "Athletic Performance",
            "detox": "Detox",
        }
        user.goals = []
        if goal_code:
            goal_name = goal_map.get(
                goal_code, str(goal_code).replace("_", " ").title()
            )
            goal = GoalsTable.query.filter(GoalsTable.name.ilike(goal_name)).first()
            if not goal:
                goal = GoalsTable(name=goal_name, description="User-selected goal")
                db.session.add(goal)
            user.goals = [goal]

        plan = DashboardService._build_user_diet_plan(
            personal=personal,
            health=health,
            preferences=payload.get("preferences", {}) or {},
        )
        safe_plan = DashboardService._to_json_safe(plan)
        DashboardService._apply_goal_from_plan(user, safe_plan)
        metrics = safe_plan.get("metrics", {})

        result_payload = {
            "form_data": payload,
            "metrics": metrics,
            "plan": safe_plan,
        }

        user_result = UserResultsTable(
            user_id=user.id,
            bmi=metrics.get("bmi"),
            status="completed",
            result_data=json.dumps(result_payload, default=str),
            generated_at=datetime.utcnow(),
        )
        db.session.add(user_result)
        db.session.commit()

        return {
            "result_id": user_result.id,
            **safe_plan,
        }

    @staticmethod
    def get_recent_activities(limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent system activities"""
        try:
            activities = []

            # Recent user registrations
            recent_users = (
                UserTable.query.order_by(UserTable.created_at.desc()).limit(5).all()
            )
            for user in recent_users:
                activities.append(
                    {
                        "timestamp": user.created_at.isoformat(),
                        "title": "New User Registration",
                        "description": f"{user.full_name} registered as a new user",
                        "type": "user",
                        "icon": "user-plus",
                    }
                )

            # Recent diagnoses
            recent_diagnoses = (
                UserResultsTable.query.order_by(UserResultsTable.created_at.desc())
                .limit(5)
                .all()
            )
            for diagnosis in recent_diagnoses:
                activities.append(
                    {
                        "timestamp": diagnosis.created_at.isoformat(),
                        "title": "New Diagnosis",
                        "description": f"Diagnosis completed for user {diagnosis.user.full_name}",
                        "type": "diagnosis",
                        "icon": "stethoscope",
                    }
                )

            # Sort by timestamp and limit
            activities.sort(key=lambda x: x["timestamp"], reverse=True)
            return activities[:limit]
        except Exception as e:
            logger.error(f"Error getting recent activities: {e}")
            return []

    @staticmethod
    def run_diagnosis(symptoms: List[Dict[str, Any]], user_id: int) -> Dict[str, Any]:
        """Run diagnosis based on symptoms using inference engine"""
        try:
            # This is a simplified diagnosis engine
            # In a real implementation, this would use sophisticated rule-based reasoning

            # Analyze symptoms to find potential conditions
            potential_conditions = DashboardService._analyze_symptoms(symptoms)

            # Get primary diagnosis (highest confidence)
            primary_diagnosis = (
                potential_conditions[0]
                if potential_conditions
                else {
                    "name": "No specific condition identified",
                    "description": "Based on the provided symptoms, no specific condition could be identified. Please consult with a healthcare professional.",
                    "confidence": 0,
                }
            )

            # Generate recommendations based on symptoms and potential conditions
            recommendations = DashboardService._generate_recommendations(
                symptoms, primary_diagnosis
            )

            # Generate next steps
            next_steps = DashboardService._generate_next_steps(
                primary_diagnosis, symptoms
            )

            # Save diagnosis result
            diagnosis_data = {
                "symptoms": symptoms,
                "primary_diagnosis": primary_diagnosis,
                "all_conditions": potential_conditions,
                "recommendations": recommendations,
                "next_steps": next_steps,
                "timestamp": datetime.utcnow().isoformat(),
            }

            result_payload = {
                "type": "diagnosis",
                "diagnosis": diagnosis_data,
            }

            user_result = UserResultsTable(
                user_id=user_id,
                status="completed",
                result_data=json.dumps(result_payload),
                created_at=datetime.utcnow(),
            )
            db.session.add(user_result)
            db.session.commit()

            return {
                "primary_diagnosis": primary_diagnosis,
                "recommendations": recommendations,
                "next_steps": next_steps,
                "result_id": user_result.id,
                "all_conditions": potential_conditions,
            }
        except Exception as e:
            logger.error(f"Error running diagnosis: {e}")
            raise

    @staticmethod
    def get_diet_recommendations(
        user_id: int, goal_id: int
    ) -> List[Dict[str, Any]]:
        """Get diet recommendations based on user's goals"""
        try:
            goal = GoalsTable.query.get(goal_id)

            if not goal:
                return []

            matching_rules = DietRulesTable.query.filter(
                DietRulesTable.goals.contains(goal),
            ).all()

            recommendations = []
            for rule in matching_rules:
                recommendations.append(
                    {
                        "rule_id": rule.id,
                        "name": rule.name,
                        "description": rule.description,
                        "restrictions": (
                            rule.restrictions.split(",") if rule.restrictions else []
                        ),
                        "recommendations": (
                            rule.recommendations.split(",")
                            if rule.recommendations
                            else []
                        ),
                        "meal_plan": rule.meal_plan,
                    }
                )

            return recommendations
        except Exception as e:
            logger.error(f"Error getting diet recommendations: {e}")
            return []

    @staticmethod
    def calculate_bmi(height_cm: float, weight_kg: float) -> Dict[str, Any]:
        """Calculate BMI and return category"""
        try:
            height_m = height_cm / 100
            bmi = round(weight_kg / (height_m**2), 2)

            category = DashboardService._get_bmi_category(bmi)

            return {
                "bmi": bmi,
                "category": category,
                "height": height_cm,
                "weight": weight_kg,
                "status": (
                    "normal" if category == "Normal weight" else "attention_needed"
                ),
            }
        except Exception as e:
            logger.error(f"Error calculating BMI: {e}")
            return {}

    @staticmethod
    def export_data(data_type: str, format_type: str = "json") -> Dict[str, Any]:
        """Export system data in specified format"""
        try:
            data = []

            if data_type == "users":
                users = UserTable.query.all()
                data = [
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                        "roles": [role.name for role in user.roles],
                        "created_at": user.created_at.isoformat(),
                        "is_active": user.is_active,
                    }
                    for user in users
                ]

            elif data_type == "rules":
                rules = DietRulesTable.query.all()
                data = [
                    {
                        "id": rule.id,
                        "name": rule.name,
                        "description": rule.description,
                        "created_at": rule.created_at.isoformat(),
                    }
                    for rule in rules
                ]

            elif data_type == "diagnoses":
                diagnoses = UserResultsTable.query.all()
                data = [
                    {
                        "id": diagnosis.id,
                        "user_id": diagnosis.user_id,
                        "status": diagnosis.status,
                        "created_at": diagnosis.created_at.isoformat(),
                    }
                    for diagnosis in diagnoses
                ]

            return {
                "data": data,
                "format": format_type,
                "exported_at": datetime.utcnow().isoformat(),
                "total_records": len(data),
            }
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return {}

    @staticmethod
    def _build_user_diet_plan(
        personal: Dict[str, Any],
        health: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build diet plan based on rule conditions and mapped foods."""
        profile = DashboardService._build_profile(personal, health, preferences)
        matched_rule = None
        try:
            matched_rule = DashboardService._select_matching_rule(profile)
        except Exception:
            logger.exception("Failed to select matching rule")
        foods = []
        avoid_foods = []
        actions = []
        rule_summary = None

        if matched_rule:
            try:
                rule = matched_rule["rule"]
                actions = matched_rule.get("actions", []) or []
                foods = DashboardService._get_rule_foods(rule.id)
                avoid_foods = DashboardService._get_rule_avoid_foods(rule.id)
                rule_summary = {
                    "id": rule.id,
                    "name": rule.rule_name,
                    "description": rule.description or "",
                    "priority": matched_rule.get("priority", "medium"),
                    "conditions": matched_rule.get("conditions", []),
                }
            except Exception:
                logger.exception("Failed to build rule outputs")
                foods = []
                avoid_foods = []
                actions = []
                rule_summary = None

        action_metrics = DashboardService._extract_action_metrics(actions)
        metrics = DashboardService._calculate_user_metrics(personal, action_metrics)

        return {
            "profile": profile,
            "metrics": metrics,
            "rule": rule_summary,
            "foods": foods,
            "avoid_foods": avoid_foods,
        }

    @staticmethod
    def _build_profile(
        personal: Dict[str, Any],
        health: Dict[str, Any],
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize profile values for rule evaluation and UI."""

        def to_int(value):
            try:
                return int(value)
            except Exception:
                return None

        def to_float(value):
            try:
                return float(value)
            except Exception:
                return None

        age = to_int(personal.get("age"))
        weight = to_float(personal.get("weight"))
        height = to_float(personal.get("height"))
        height_m = height / 100 if height else None
        bmi = round(weight / (height_m**2), 2) if weight and height_m else None

        gender = str(personal.get("gender") or "").strip().lower()
        diet_type = str(health.get("dietType") or "").strip().lower()
        allergies = health.get("allergies") or []
        if not isinstance(allergies, list):
            allergies = [allergies]
        allergies = [
            str(item).strip().lower() for item in allergies if str(item).strip()
        ]
        meals_per_day = to_int(preferences.get("mealsPerDay"))

        return {
            "age": age,
            "gender": gender,
            "weight": weight,
            "height": height,
            "bmi": bmi,
            "diet_type": diet_type,
            "allergies": allergies,
            "meals_per_day": meals_per_day,
        }

    @staticmethod
    def _select_matching_rule(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select best matching diet rule based on profile."""
        rules = DietRulesTable.query.all()
        matched = []
        for rule in rules:
            meta = DashboardService._parse_rule_meta(rule)
            if not meta.get("active", True):
                continue
            conditions = meta.get("conditions", []) or []
            if not conditions:
                continue
            if DashboardService._rule_matches_profile(conditions, profile):
                matched.append({**meta, "rule": rule})

        if not matched:
            return None

        priority_rank = {"high": 3, "medium": 2, "low": 1}
        matched.sort(
            key=lambda item: (
                priority_rank.get(str(item.get("priority", "")).lower(), 0),
                item["rule"].created_at or datetime.min,
            ),
            reverse=True,
        )
        return matched[0]

    @staticmethod
    def _parse_rule_meta(rule: DietRulesTable) -> Dict[str, Any]:
        """Parse rule metadata from stored conditions JSON."""
        meta = {
            "conditions": [],
            "actions": [],
            "priority": "medium",
            "active": True,
            "category": "diet",
        }

        raw = rule.conditions or ""
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None

        if isinstance(parsed, dict):
            meta["conditions"] = parsed.get("conditions") or []
            meta["actions"] = parsed.get("actions") or []
            meta["priority"] = parsed.get("priority", meta["priority"])
            meta["active"] = bool(parsed.get("active", meta["active"]))
            meta["category"] = parsed.get("category", meta["category"])

        if hasattr(rule, "is_active") and rule.is_active is not None:
            meta["active"] = bool(rule.is_active)

        if isinstance(parsed, dict):
            return meta

        if isinstance(parsed, list):
            meta["conditions"] = parsed
            if hasattr(rule, "is_active") and rule.is_active is not None:
                meta["active"] = bool(rule.is_active)
            return meta

        if raw:
            parts = [part.strip() for part in raw.replace(";", ",").split(",")]
            meta["conditions"] = [part for part in parts if part]
        if hasattr(rule, "is_active") and rule.is_active is not None:
            meta["active"] = bool(rule.is_active)
        return meta

    @staticmethod
    def _rule_matches_profile(conditions: List[str], profile: Dict[str, Any]) -> bool:
        """Check if all rule conditions match the user profile."""
        for condition in conditions:
            if not DashboardService._evaluate_condition(condition, profile):
                return False
        return True

    @staticmethod
    def _evaluate_condition(condition: str, profile: Dict[str, Any]) -> bool:
        if not condition:
            return False
        if not isinstance(condition, str):
            try:
                condition = str(condition)
            except Exception:
                return False

        normalized = condition.strip().lower()
        if normalized.startswith("recommend foods:") or normalized.startswith(
            "avoid foods:"
        ):
            return True

        parts = condition.strip().split()
        if len(parts) < 3:
            return False

        param = parts[0].lower()
        operator = parts[1].lower()
        raw_value = " ".join(parts[2:]).strip()
        value_lower = raw_value.lower()

        profile_value = None
        if param in ["age", "weight", "height", "bmi", "meals_per_day"]:
            profile_value = profile.get(param)
        elif param in ["allergy", "allergies"]:
            profile_value = profile.get("allergies", [])
        elif param in ["diet_type", "gender"]:
            profile_value = profile.get(param)

        if operator == "equals":
            if isinstance(profile_value, list):
                return value_lower in [str(item).lower() for item in profile_value]
            if isinstance(profile_value, (int, float)):
                try:
                    return profile_value == float(raw_value)
                except Exception:
                    return False
            return str(profile_value or "").lower() == value_lower

        if operator == "not_equals":
            return not DashboardService._evaluate_condition(
                f"{param} equals {raw_value}", profile
            )

        if operator in ["greater_than", "less_than"]:
            try:
                numeric_value = float(raw_value)
                if profile_value is None:
                    return False
                if operator == "greater_than":
                    return float(profile_value) > numeric_value
                return float(profile_value) < numeric_value
            except Exception:
                return False

        if operator in ["contains", "not_contains"]:
            if isinstance(profile_value, list):
                contains = value_lower in [str(item).lower() for item in profile_value]
            else:
                contains = value_lower in str(profile_value or "").lower()
            return contains if operator == "contains" else not contains

        return False

    @staticmethod
    def _infer_goal_label(
        rule_name: Optional[str],
        conditions: List[str],
        profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        name_text = str(rule_name or "").lower()
        condition_text = " ".join([str(item) for item in (conditions or [])]).lower()
        combined = f"{name_text} {condition_text}".strip()

        if any(
            token in combined
            for token in [
                "lose",
                "loss",
                "reduce",
                "cut",
                "slim",
                "overweight",
                "obese",
            ]
        ):
            return "Lose Weight"
        if any(
            token in combined
            for token in [
                "gain",
                "increase",
                "bulking",
                "underweight",
                "thin",
                "thinness",
            ]
        ):
            return "Gain Weight"
        if any(token in combined for token in ["maintain", "maintenance", "balance"]):
            return "Maintain Weight"

        bmi_min = None
        bmi_max = None
        for condition in conditions or []:
            text = str(condition or "").strip().lower()
            if not text:
                continue
            parts = text.split()
            if len(parts) < 3 or parts[0] != "bmi":
                continue
            operator = parts[1]
            raw_value = " ".join(parts[2:]).strip()
            try:
                value = float(raw_value)
            except Exception:
                continue
            if operator == "greater_than":
                bmi_min = value if bmi_min is None else max(bmi_min, value)
            elif operator == "less_than":
                bmi_max = value if bmi_max is None else min(bmi_max, value)

        if bmi_max is not None and bmi_max <= 18.5:
            return "Gain Weight"
        if bmi_min is not None and bmi_min >= 25:
            return "Lose Weight"
        if (
            bmi_min is not None
            and bmi_max is not None
            and bmi_min >= 18.5
            and bmi_max <= 25
        ):
            return "Maintain Weight"

        bmi_value = None
        try:
            bmi_value = float((profile or {}).get("bmi"))
        except Exception:
            bmi_value = None

        if bmi_value is not None:
            if bmi_value < 18.5:
                return "Gain Weight"
            if bmi_value >= 25:
                return "Lose Weight"
            return "Maintain Weight"

        return None

    @staticmethod
    def _ensure_base_goals() -> None:
        base_goals = {
            "Lose Weight": "Reduce body weight safely and steadily.",
            "Maintain Weight": "Keep current weight stable and healthy.",
            "Gain Weight": "Increase body weight in a healthy way.",
        }
        existing = {
            goal.name.lower(): goal
            for goal in GoalsTable.query.filter(
                GoalsTable.name.in_(list(base_goals.keys()))
            ).all()
        }
        for name, description in base_goals.items():
            if name.lower() not in existing:
                db.session.add(GoalsTable(name=name, description=description))
        db.session.flush()

    @staticmethod
    def _get_or_create_goal(goal_name: Optional[str]) -> Optional[GoalsTable]:
        name = (goal_name or "").strip()
        if not name:
            return None
        DashboardService._ensure_base_goals()
        goal = GoalsTable.query.filter(GoalsTable.name.ilike(name)).first()
        if not goal:
            goal = GoalsTable(
                name=name,
                description="Auto-assigned from diet rule matching.",
            )
            db.session.add(goal)
            db.session.flush()
        return goal

    @staticmethod
    def _apply_goal_from_plan(user: UserTable, plan: Dict[str, Any]) -> None:
        rule_info = (plan or {}).get("rule") or {}
        if not rule_info:
            return
        goal_label = DashboardService._infer_goal_label(
            rule_info.get("name"),
            rule_info.get("conditions") or [],
            (plan or {}).get("profile") or {},
        )
        if not goal_label:
            return
        goal = DashboardService._get_or_create_goal(goal_label)
        if not goal:
            return

        user.goals = [goal]

        rule_id = rule_info.get("id")
        if rule_id:
            rule = DietRulesTable.query.get(rule_id)
            if rule:
                GoalsTable.query.filter(
                    GoalsTable.diet_rule_id == rule.id
                ).update({"diet_rule_id": None}, synchronize_session=False)
                rule.goals = [goal]
                goal.diet_rule_id = rule.id
    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        """Convert value to JSON-serializable types."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): DashboardService._to_json_safe(val)
                for key, val in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [DashboardService._to_json_safe(item) for item in value]
        try:
            return float(value)
        except Exception:
            return str(value)

    @staticmethod
    def _get_rule_foods(rule_id: int) -> List[Dict[str, Any]]:
        """Get recommended foods for a rule (excluding avoided items)."""
        if not rule_id:
            return []
        food_maps = RuleFoodMapTable.query.filter_by(diet_rule_id=rule_id).all()
        foods = []
        for mapping in food_maps:
            note = (mapping.notes or "").strip().lower()
            if note == "avoid":
                continue
            food = mapping.food
            if not food:
                continue
            foods.append(
                {
                    "id": food.id,
                    "name": food.name,
                    "calories": food.calories,
                    "protein": food.protein,
                    "carbs": food.carbs,
                    "fat": food.fat,
                }
            )
        return foods

    @staticmethod
    def _get_rule_avoid_foods(rule_id: int) -> List[Dict[str, Any]]:
        """Get avoided foods for a rule."""
        if not rule_id:
            return []
        food_maps = RuleFoodMapTable.query.filter_by(diet_rule_id=rule_id).all()
        foods = []
        for mapping in food_maps:
            note = (mapping.notes or "").strip().lower()
            if note != "avoid":
                continue
            food = mapping.food
            if not food:
                continue
            foods.append(
                {
                    "id": food.id,
                    "name": food.name,
                    "calories": food.calories,
                    "protein": food.protein,
                    "carbs": food.carbs,
                    "fat": food.fat,
                }
            )
        return foods

    @staticmethod
    def _extract_action_metrics(actions: List[str]) -> Dict[str, Optional[float]]:
        """Extract calories and macro targets from rule actions."""
        metrics = {"calories": None, "protein": None, "carbs": None, "fat": None}
        if not actions:
            return metrics

        for action in actions:
            text = str(action)
            lower = text.lower()
            if "set_calories" in lower:
                match = re.search(r"calories\s*=\s*(\d+(?:\.\d+)?)", lower)
                if not match:
                    match = re.search(r"(\d+(?:\.\d+)?)", lower)
                if match:
                    metrics["calories"] = float(match.group(1))

            if "set_macros" in lower:
                for key in ["protein", "carbs", "fat"]:
                    match = re.search(rf"{key}\s*=\s*(\d+(?:\.\d+)?)", lower)
                    if match:
                        metrics[key] = float(match.group(1))

        return metrics

    @staticmethod
    def _calculate_user_metrics(
        personal: Dict[str, Any],
        action_metrics: Dict[str, Optional[float]],
    ) -> Dict[str, Optional[float]]:
        """Calculate BMI and macro targets, using rule actions when available."""
        metrics = {
            "bmi": None,
            "calories": action_metrics.get("calories"),
            "protein": action_metrics.get("protein"),
            "carbs": action_metrics.get("carbs"),
            "fat": action_metrics.get("fat"),
        }

        try:
            weight = float(personal.get("weight", 0) or 0)
            height_cm = float(personal.get("height", 0) or 0)
            age = int(personal.get("age", 0) or 0)
            gender = str(personal.get("gender", "") or "").lower()

            if weight > 0 and height_cm > 0:
                height_m = height_cm / 100
                metrics["bmi"] = round(weight / (height_m**2), 1)

            if (
                metrics["calories"] is None
                and metrics["protein"]
                and metrics["carbs"]
                and metrics["fat"]
            ):
                metrics["calories"] = (
                    metrics["protein"] * 4 + metrics["carbs"] * 4 + metrics["fat"] * 9
                )

            if metrics["calories"] is None and weight > 0 and height_cm > 0 and age > 0:
                if gender == "male":
                    bmr = 10 * weight + 6.25 * height_cm - 5 * age + 5
                else:
                    bmr = 10 * weight + 6.25 * height_cm - 5 * age - 161
                metrics["calories"] = bmr * 1.2

            if metrics["calories"]:
                calories = float(metrics["calories"])
                if not metrics["protein"]:
                    metrics["protein"] = calories * 0.3 / 4
                if not metrics["carbs"]:
                    metrics["carbs"] = calories * 0.45 / 4
                if not metrics["fat"]:
                    metrics["fat"] = calories * 0.25 / 9

            for key in ["calories", "protein", "carbs", "fat"]:
                if metrics[key] is not None:
                    metrics[key] = round(float(metrics[key]), 0)
        except Exception as e:
            logger.error(f"Error calculating user metrics: {e}")

        return metrics

    @staticmethod
    def _calculate_nutrition_metrics(
        personal: Dict[str, Any], goal_code: Optional[str]
    ) -> Dict[str, Any]:
        """Calculate BMI, BMR, TDEE, and daily calories."""
        try:
            weight = float(personal.get("weight", 0) or 0)
            height_cm = float(personal.get("height", 0) or 0)
            age = int(personal.get("age", 0) or 0)
            gender = str(personal.get("gender", "") or "").lower()
            activity = str(personal.get("activity", "") or "").lower()

            if weight <= 0 or height_cm <= 0 or age <= 0:
                return {}

            height_m = height_cm / 100
            bmi = round(weight / (height_m**2), 2)

            if gender == "male":
                bmr = 10 * weight + 6.25 * height_cm - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height_cm - 5 * age - 161

            activity_multipliers = {
                "sedentary": 1.2,
                "light": 1.375,
                "moderate": 1.55,
                "active": 1.725,
                "athlete": 1.9,
            }
            tdee = bmr * activity_multipliers.get(activity, 1.2)

            daily_calories = tdee
            if goal_code == "weight_loss":
                daily_calories = tdee - 500
            elif goal_code == "muscle_gain":
                daily_calories = tdee + 300

            return {
                "bmi": round(bmi, 2),
                "bmr": round(bmr, 0),
                "tdee": round(tdee, 0),
                "daily_calories": round(daily_calories, 0),
            }
        except Exception as e:
            logger.error(f"Error calculating nutrition metrics: {e}")
            return {}

    # Helper methods
    @staticmethod
    def _calculate_growth(entity_type: str) -> float:
        """Calculate growth percentage for the last 30 days"""
        try:
            now = datetime.utcnow()
            thirty_days_ago = now - timedelta(days=30)

            if entity_type == "users":
                current = UserTable.query.filter(
                    UserTable.created_at >= thirty_days_ago
                ).count()
                previous = UserTable.query.filter(
                    UserTable.created_at >= thirty_days_ago - timedelta(days=30),
                    UserTable.created_at < thirty_days_ago,
                ).count()
            elif entity_type == "diagnoses":
                current = UserResultsTable.query.filter(
                    UserResultsTable.created_at >= thirty_days_ago
                ).count()
                previous = UserResultsTable.query.filter(
                    UserResultsTable.created_at >= thirty_days_ago - timedelta(days=30),
                    UserResultsTable.created_at < thirty_days_ago,
                ).count()
            else:
                return 0.0

            if previous == 0:
                return 100.0 if current > 0 else 0.0

            return round(((current - previous) / previous) * 100, 2)
        except Exception as e:
            logger.error(f"Error calculating growth: {e}")
            return 0.0

    @staticmethod
    def _get_bmi_category(bmi: float) -> str:
        """Get BMI category based on BMI value"""
        if bmi < 18.5:
            return "Underweight"
        elif 18.5 <= bmi < 25:
            return "Normal weight"
        elif 25 <= bmi < 30:
            return "Overweight"
        else:
            return "Obese"

    @staticmethod
    def _analyze_symptoms(symptoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze symptoms to identify potential conditions"""
        # Simplified symptom analysis
        # In a real implementation, this would use a sophisticated medical knowledge base

        symptom_keywords = [symptom.get("name", "").lower() for symptom in symptoms]
        symptom_severities = [symptom.get("severity", "mild") for symptom in symptoms]

        conditions = []

        # Diabetes indicators
        diabetes_indicators = [
            "thirst",
            "urination",
            "fatigue",
            "weight loss",
            "blurred vision",
        ]
        diabetes_score = sum(
            1
            for indicator in diabetes_indicators
            if any(indicator in keyword for keyword in symptom_keywords)
        )

        if diabetes_score >= 3:
            conditions.append(
                {
                    "name": "Type 2 Diabetes Risk",
                    "description": "Based on your symptoms, you may be at risk for Type 2 Diabetes",
                    "confidence": min(diabetes_score * 20, 85),
                    "severity": "moderate" if diabetes_score < 4 else "high",
                }
            )

        # Hypertension indicators
        hypertension_indicators = ["headache", "dizziness", "fatigue", "chest pain"]
        hypertension_score = sum(
            1
            for indicator in hypertension_indicators
            if any(indicator in keyword for keyword in symptom_keywords)
        )

        if hypertension_score >= 2:
            conditions.append(
                {
                    "name": "Hypertension Risk",
                    "description": "Based on your symptoms, you may be at risk for Hypertension",
                    "confidence": min(hypertension_score * 25, 75),
                    "severity": "moderate" if hypertension_score < 3 else "high",
                }
            )

        # Sort by confidence
        conditions.sort(key=lambda x: x["confidence"], reverse=True)
        return conditions

    @staticmethod
    def _generate_recommendations(
        symptoms: List[Dict[str, Any]], diagnosis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on symptoms and diagnosis"""
        recommendations = [
            "Consult with a healthcare professional for proper diagnosis",
            "Monitor your symptoms and keep a health journal",
            "Maintain a balanced and healthy diet",
            "Engage in regular physical activity",
        ]

        # Add specific recommendations based on diagnosis
        if "diabetes" in diagnosis.get("name", "").lower():
            recommendations.extend(
                [
                    "Monitor blood sugar levels regularly",
                    "Reduce intake of refined sugars and carbohydrates",
                    "Increase fiber intake through whole grains and vegetables",
                    "Stay well hydrated",
                ]
            )

        if "hypertension" in diagnosis.get("name", "").lower():
            recommendations.extend(
                [
                    "Reduce sodium intake",
                    "Limit alcohol consumption",
                    "Practice stress management techniques",
                    "Monitor blood pressure regularly",
                ]
            )

        return recommendations

    @staticmethod
    def _generate_next_steps(
        diagnosis: Dict[str, Any], symptoms: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate next steps for the user"""
        steps = [
            "Schedule an appointment with your primary care physician",
            "Prepare a list of all symptoms and their duration",
            "Gather your medical history and current medications",
        ]

        if diagnosis.get("confidence", 0) > 70:
            steps.append("Consider seeking specialist consultation based on diagnosis")

        if any(symptom.get("severity") == "severe" for symptom in symptoms):
            steps.insert(0, "Seek immediate medical attention for severe symptoms")

        return steps

    @staticmethod
    def _get_today_consultations(doctor_id: int) -> int:
        """Get number of consultations for today"""
        # Simplified - would query actual consultation records
        return 5

    @staticmethod
    def _get_week_consultations(doctor_id: int) -> int:
        """Get number of consultations for this week"""
        # Simplified - would query actual consultation records
        return 25

    @staticmethod
    def _get_recent_patients(doctor_id: int) -> int:
        """Get number of recent patients"""
        # Simplified - would query actual patient records
        return 10

    @staticmethod
    def _get_upcoming_appointments(doctor_id: int) -> int:
        """Get number of upcoming appointments"""
        # Simplified - would query actual appointment records
        return 8

    @staticmethod
    def _get_user_appointments(user_id: int) -> int:
        """Get number of user's upcoming appointments"""
        # Simplified - would query actual appointment records
        return 2

    @staticmethod
    def _calculate_health_score(user: UserTable) -> int:
        """Calculate overall health score for user"""
        # Simplified health score calculation
        base_score = 70

        # Adjust based on number of active goals
        goal_bonus = min(len(user.goals) * 5, 20)

        # Adjust based on recent diagnoses
        recent_diagnoses = len(
            [r for r in user.user_results if r.status == "completed"]
        )
        diagnosis_bonus = min(recent_diagnoses * 3, 15)

        total_score = base_score + goal_bonus + diagnosis_bonus
        return min(total_score, 100)

    @staticmethod
    def _get_recommendations_count(user_id: int) -> int:
        """Get count of active recommendations for user"""
        # Simplified - would query actual recommendation records
        return 5
