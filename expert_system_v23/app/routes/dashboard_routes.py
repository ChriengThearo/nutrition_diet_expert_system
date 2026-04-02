from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    current_app,
)
from flask_login import login_required, current_user
from functools import wraps
from app.models.user import UserTable
from app.models.role import RoleTable
from app.models.goal import GoalsTable
from app.models.diet_rule import DietRulesTable
from app.models.food import FoodsTable
from app.models.rule_food_map import RuleFoodMapTable
from app.models.user_result import UserResultsTable
from app.forms.dashboard_forms import UserProfileEditForm
from app.services.dashboard_services import DashboardService
from app.services.diet_rule_service import DietRuleService
from app.routes.access_control import permission_required
from extensions import db, csrf
from datetime import datetime, timedelta
import json
import os
import uuid
from werkzeug.utils import secure_filename

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


# Role-based access decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Login required", "danger")
            return redirect(url_for("auth.login"))
        if current_user.has_role("admin") or current_user.has_permission(
            "dashboard.admin"
        ):
            return f(*args, **kwargs)
        flash("Admin access required", "danger")
        return redirect(url_for("dashboard.dashboard_home"))

    return decorated_function


def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Login required", "danger")
            return redirect(url_for("auth.login"))
        if current_user.has_role("doctor") or current_user.has_permission(
            "dashboard.doctor"
        ):
            return f(*args, **kwargs)
        flash("Doctor access required", "danger")
        return redirect(url_for("dashboard.dashboard_home"))

    return decorated_function


def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Login required", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


# Admin Dashboard Routes
@dashboard_bp.route("/admin")
@login_required
@admin_required
@permission_required(
    "dashboard.admin", "You have no permission to access the admin dashboard."
)
def admin_dashboard():
    """Admin dashboard main page"""
    # Get statistics
    total_users = UserTable.query.count()
    total_doctors = (
        UserTable.query.join(UserTable.roles).filter(RoleTable.name == "doctor").count()
    )
    total_rules = DietRulesTable.query.count()

    return render_template(
        "dashboard/admin_dashboard.html",
        total_users=total_users,
        total_doctors=total_doctors,
        total_rules=total_rules,
    )


@dashboard_bp.route("/admin/data")
@login_required
@admin_required
@permission_required(
    "dashboard.admin",
    "You have no permission to access the admin dashboard data.",
    json_response=True,
)
def admin_dashboard_data():
    """Admin dashboard data API endpoint"""
    # Get recent activities
    activities = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "title": "New User Registration",
            "description": "John Doe registered as a new user",
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "title": "Rule Created",
            "description": "Dr. Smith created a new diet rule for weight loss",
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
            "title": "System Update",
            "description": "Knowledge base updated with new goals and foods",
        },
    ]

    return jsonify(
        {
            "total_users": UserTable.query.count(),
            "total_doctors": UserTable.query.join(UserTable.roles)
            .filter(RoleTable.name == "doctor")
            .count(),
            "total_rules": DietRulesTable.query.count(),
            "activities": activities,
        }
    )


@dashboard_bp.route("/admin/audit-log")
@login_required
@admin_required
@permission_required(
    "system.audit", "You have no permission to view the audit log.", json_response=True
)
def audit_log():
    """Get audit log data"""
    audit_data = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "user": "Admin User",
            "action": "Created new user",
            "details": "Created user: testuser@example.com",
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "user": "Dr. Smith",
            "action": "Modified diet rule",
            "details": "Updated rule ID: 123",
        },
    ]

    return jsonify(audit_data)


# Doctor Dashboard Routes
@dashboard_bp.route("/doctor")
@login_required
@doctor_required
@permission_required(
    "dashboard.doctor", "You have no permission to access the doctor dashboard."
)
def doctor_dashboard():
    """Doctor dashboard main page"""
    # Get doctor-specific statistics
    total_patients = (
        UserTable.query.count()
    )  # Simplified - would filter by doctor's patients
    consultations_today = 5  # Simplified - would count today's consultations
    pending_diagnoses = UserResultsTable.query.filter_by(status="pending").count()
    rules_authored = (
        DietRulesTable.query.count()
    )  # Simplified - would filter by doctor's rules

    return render_template(
        "dashboard/doctor_dashboard.html",
        total_patients=total_patients,
        consultations_today=consultations_today,
        pending_diagnoses=pending_diagnoses,
        rules_authored=rules_authored,
    )


@dashboard_bp.route("/doctor/data")
@login_required
@doctor_required
@permission_required(
    "dashboard.doctor",
    "You have no permission to access the doctor dashboard data.",
    json_response=True,
)
def doctor_dashboard_data():
    """Doctor dashboard data API endpoint"""
    consultations = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "patient_name": "Alice Johnson",
            "reason": "Diabetes management consultation",
        },
        {
            "timestamp": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
            "patient_name": "Bob Smith",
            "reason": "Nutrition assessment",
        },
    ]

    return jsonify(
        {
            "total_patients": UserTable.query.count(),
            "consultations_today": 5,
            "pending_diagnoses": UserResultsTable.query.filter_by(
                status="pending"
            ).count(),
            "rules_authored": DietRulesTable.query.count(),
            "consultations": consultations,
        }
    )


@dashboard_bp.route("/doctor/rules")
@login_required
@doctor_required
@permission_required(
    "rule.read", "You have no permission to view rules.", json_response=True
)
def doctor_rules():
    """Return diet rules for doctor dashboard"""
    rules = DietRuleService.get_diet_rule_all()
    result = []

    for rule in rules:
        conditions = []
        category = "diet"
        priority = "medium"
        active = bool(getattr(rule, "is_active", True))
        actions = []
        recommended_ids = []
        excluded_ids = []

        if rule.conditions:
            try:
                parsed = json.loads(rule.conditions)
                if isinstance(parsed, dict):
                    conditions.extend(
                        [str(item) for item in parsed.get("conditions", [])]
                    )
                    actions = parsed.get("actions") or []
                    category = parsed.get("category", category)
                    priority = parsed.get("priority", priority)
                    recommended_ids = parsed.get("recommended_food_ids") or []
                    excluded_ids = parsed.get("excluded_food_ids") or []
                elif isinstance(parsed, list):
                    conditions.extend([str(item) for item in parsed])
                else:
                    conditions.append(str(parsed))
            except Exception:
                raw_parts = [
                    part.strip()
                    for part in rule.conditions.replace(";", ",").split(",")
                ]
                conditions.extend([part for part in raw_parts if part])

        if rule.goals:
            conditions.extend([f"goal = {goal.name}" for goal in rule.goals])

        if rule.goals and category == "diet":
            category = "goal"

        if not recommended_ids and not excluded_ids:
            for mapping in rule.rule_food_maps or []:
                if mapping.notes == "recommended":
                    recommended_ids.append(mapping.food_id)
                elif mapping.notes == "avoid":
                    excluded_ids.append(mapping.food_id)

        result.append(
            {
                "id": rule.id,
                "name": rule.rule_name,
                "category": category,
                "priority": priority,
                "active": active,
                "conditions": conditions,
                "actions": actions if isinstance(actions, list) else [],
                "description": rule.description or "",
                "recommended_food_ids": recommended_ids,
                "excluded_food_ids": excluded_ids,
            }
        )

    return jsonify({"rules": result})


@dashboard_bp.route("/doctor/test-plan", methods=["POST"])
@login_required
@doctor_required
@csrf.exempt
@permission_required(
    "rule.test", "You have no permission to test rules.", json_response=True
)
def doctor_test_plan():
    """Generate a diet plan for doctor test profiles."""
    payload = request.get_json(silent=True) or {}
    try:
        plan = DashboardService._build_user_diet_plan(
            personal=payload.get("personal", {}) or {},
            health=payload.get("health", {}) or {},
            preferences=payload.get("preferences", {}) or {},
        )
        return jsonify({"success": True, **plan})
    except Exception:
        current_app.logger.exception("Failed to generate doctor test plan")
        return (
            jsonify({"success": False, "message": "Failed to generate diet plan"}),
            500,
        )


@dashboard_bp.route("/doctor/foods", methods=["GET"])
@login_required
@doctor_required
@permission_required(
    "food.read", "You have no permission to view foods.", json_response=True
)
def doctor_foods():
    """Return foods for doctor dashboard"""
    foods = FoodsTable.query.order_by(FoodsTable.created_at.desc()).limit(100).all()
    return jsonify(
        {
            "foods": [
                {
                    "id": food.id,
                    "name": food.name,
                    "photo": food.photo,
                    "description": food.description or "",
                    "is_vegan": 1 if getattr(food, "is_gevan", False) else 0,
                    "food_type": getattr(food, "food_type", "general") or "general",
                    "calories": food.calories,
                    "protein": food.protein,
                    "carbs": food.carbs,
                    "fat": food.fat,
                }
                for food in foods
            ]
        }
    )


@dashboard_bp.route("/doctor/foods", methods=["POST"])
@login_required
@doctor_required
@csrf.exempt
@permission_required(
    "food.create", "You have no permission to create foods.", json_response=True
)
def create_doctor_food():
    payload = request.get_json(silent=True) or {}
    form_data = request.form or {}
    name = (payload.get("name") or form_data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Food name is required"}), 400
    allowed_food_types = {"general", "seafood", "eggs", "soy"}

    def to_float(value):
        try:
            return (
                float(value)
                if value
                not in (
                    None,
                    "",
                )
                else None
            )
        except Exception:
            return None

    def get_value(key):
        return payload.get(key) if key in payload else form_data.get(key)

    def to_bool(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y", "on"}

    photo_path = None
    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        filename = secure_filename(photo_file.filename)
        _, ext = os.path.splitext(filename)
        safe_ext = ext if ext else ""
        unique_name = f"food_{uuid.uuid4().hex}{safe_ext}"
        project_root = os.path.dirname(current_app.root_path)
        upload_dir = os.path.join(project_root, "images", "foods")
        os.makedirs(upload_dir, exist_ok=True)
        photo_file.save(os.path.join(upload_dir, unique_name))
        photo_path = f"images/foods/{unique_name}"

    food = FoodsTable(
        name=name,
        photo=photo_path or (get_value("photo") or "").strip() or None,
        description=(get_value("description") or "").strip(),
        food_type=(get_value("food_type") or "general").strip().lower(),
        calories=to_float(get_value("calories")),
        protein=to_float(get_value("protein")),
        carbs=to_float(get_value("carbs")),
        fat=to_float(get_value("fat")),
    )
    if food.food_type not in allowed_food_types:
        food.food_type = "general"
    vegan_value = to_bool(get_value("is_gevan"))
    if vegan_value is not None:
        food.is_gevan = vegan_value

    try:
        db.session.add(food)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "food": {
                    "id": food.id,
                    "name": food.name,
                    "photo": food.photo,
                    "description": food.description or "",
                    "food_type": food.food_type or "general",
                    "calories": food.calories,
                    "protein": food.protein,
                    "carbs": food.carbs,
                    "fat": food.fat,
                },
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to create food")
        return jsonify({"success": False, "message": "Failed to create food"}), 500


@dashboard_bp.route("/doctor/foods/<int:food_id>", methods=["POST", "DELETE"])
@login_required
@doctor_required
@csrf.exempt
def update_or_delete_doctor_food(food_id: int):
    if request.method == "DELETE":
        if not current_user.has_permission("food.delete"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You have no permission to delete food.",
                    }
                ),
                403,
            )
    else:
        if not current_user.has_permission("food.edit"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You have no permission to edit food.",
                    }
                ),
                403,
            )
    food = FoodsTable.query.get(food_id)
    if not food:
        return jsonify({"success": False, "message": "Food not found"}), 404

    if request.method == "DELETE":
        try:
            RuleFoodMapTable.query.filter_by(food_id=food.id).delete(
                synchronize_session=False
            )
            if food.photo:
                project_root = os.path.dirname(current_app.root_path)
                photo_path = os.path.join(project_root, food.photo)
                if os.path.isfile(photo_path):
                    os.remove(photo_path)
            db.session.delete(food)
            db.session.commit()
            return jsonify({"success": True})
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to delete food")
            return jsonify({"success": False, "message": "Failed to delete food"}), 500

    payload = request.get_json(silent=True) or {}
    form_data = request.form or {}
    name = (payload.get("name") or form_data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Food name is required"}), 400
    allowed_food_types = {"general", "seafood", "eggs", "soy"}

    def to_float(value):
        try:
            return float(value) if value not in (None, "") else None
        except Exception:
            return None

    def get_value(key):
        return payload.get(key) if key in payload else form_data.get(key)

    def to_bool(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y", "on"}

    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        filename = secure_filename(photo_file.filename)
        _, ext = os.path.splitext(filename)
        safe_ext = ext if ext else ""
        unique_name = f"food_{uuid.uuid4().hex}{safe_ext}"
        project_root = os.path.dirname(current_app.root_path)
        upload_dir = os.path.join(project_root, "images", "foods")
        os.makedirs(upload_dir, exist_ok=True)
        photo_file.save(os.path.join(upload_dir, unique_name))
        food.photo = f"images/foods/{unique_name}"

    food.name = name
    food.description = (get_value("description") or "").strip()
    food_type = (get_value("food_type") or "general").strip().lower()
    food.food_type = food_type if food_type in allowed_food_types else "general"
    vegan_value = to_bool(get_value("is_gevan"))
    if vegan_value is not None:
        food.is_gevan = vegan_value
    food.calories = to_float(get_value("calories"))
    food.protein = to_float(get_value("protein"))
    food.carbs = to_float(get_value("carbs"))
    food.fat = to_float(get_value("fat"))

    try:
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "food": {
                    "id": food.id,
                    "name": food.name,
                    "photo": food.photo,
                    "description": food.description or "",
                    "food_type": food.food_type or "general",
                    "calories": food.calories,
                    "protein": food.protein,
                    "carbs": food.carbs,
                    "fat": food.fat,
                },
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update food")
        return jsonify({"success": False, "message": "Failed to update food"}), 500


@dashboard_bp.route("/doctor/profile")
@login_required
@doctor_required
@permission_required(
    "dashboard.doctor", "You have no permission to view the doctor profile."
)
def doctor_profile():
    """Doctor profile page."""
    return render_template("dashboard/doctor_profile.html", user=current_user)


@dashboard_bp.route("/doctor/profile/edit", methods=["GET", "POST"])
@login_required
@doctor_required
@permission_required(
    "dashboard.doctor", "You have no permission to edit the doctor profile."
)
def doctor_profile_edit():
    """Edit doctor profile info."""
    form = UserProfileEditForm(current_user, obj=current_user)

    if form.validate_on_submit():
        current_user.username = (form.username.data or "").strip()
        current_user.full_name = (form.full_name.data or "").strip()

        photo_file = form.photo.data
        if photo_file and getattr(photo_file, "filename", ""):
            filename = secure_filename(photo_file.filename)
            _, ext = os.path.splitext(filename)
            safe_ext = ext.lower() if ext else ""
            unique_name = f"user_{current_user.id}_{uuid.uuid4().hex}{safe_ext}"
            project_root = os.path.dirname(current_app.root_path)
            upload_dir = os.path.join(project_root, "images", "profiles")
            os.makedirs(upload_dir, exist_ok=True)
            photo_file.save(os.path.join(upload_dir, unique_name))
            current_user.photo = f"images/profiles/{unique_name}"

        try:
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("dashboard.doctor_profile"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to update doctor profile")
            flash("Failed to update profile. Please try again.", "danger")

    return render_template(
        "dashboard/user_profile_edit.html",
        user=current_user,
        form=form,
        dashboard_url=url_for("dashboard.doctor_dashboard"),
        profile_url=url_for("dashboard.doctor_profile"),
        cancel_url=url_for("dashboard.doctor_profile"),
    )


@dashboard_bp.route("/doctor/rules", methods=["POST"])
@login_required
@doctor_required
@csrf.exempt
@permission_required(
    "rule.create", "You have no permission to create rules.", json_response=True
)
def create_doctor_rule():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Rule name is required"}), 400

    conditions = payload.get("conditions") or []
    if not isinstance(conditions, list):
        conditions = [str(conditions)]

    def to_int_list(values):
        if not isinstance(values, list):
            return []
        ids = []
        for item in values:
            try:
                value = int(item)
                ids.append(value)
            except Exception:
                continue
        return ids

    recommended_ids = to_int_list(payload.get("recommended_food_ids"))
    excluded_ids = to_int_list(payload.get("excluded_food_ids"))

    active = bool(payload.get("active", True))
    meta = {
        "category": payload.get("category") or "health",
        "priority": payload.get("priority") or "medium",
        "active": active,
        "conditions": conditions,
        "actions": payload.get("actions") or [],
        "recommended_food_ids": recommended_ids,
        "excluded_food_ids": excluded_ids,
    }

    try:
        rule = DietRuleService.create_diet_rule(
            {
                "rule_name": name,
                "description": payload.get("description") or "",
                "conditions": json.dumps(meta),
                "is_active": active,
            }
        )
        goal_type = (payload.get("goal_type") or "").strip().lower()
        goal_label = None
        if goal_type in {"lose", "gain", "maintain"}:
            goal_label = {
                "lose": "Lose Weight",
                "gain": "Gain Weight",
                "maintain": "Maintain Weight",
            }.get(goal_type)
        if not goal_label:
            goal_label = DashboardService._infer_goal_label(name, conditions, {})
        goal = DashboardService._get_or_create_goal(goal_label)
        if goal:
            GoalsTable.query.filter(GoalsTable.diet_rule_id == rule.id).update(
                {"diet_rule_id": None}, synchronize_session=False
            )
            rule.goals = [goal]
            goal.diet_rule_id = rule.id
            db.session.commit()

        if recommended_ids or excluded_ids:
            valid_ids = {
                food.id
                for food in FoodsTable.query.filter(
                    FoodsTable.id.in_(set(recommended_ids + excluded_ids))
                ).all()
            }
            for food_id in recommended_ids:
                if food_id in valid_ids:
                    db.session.add(
                        RuleFoodMapTable(
                            diet_rule_id=rule.id,
                            food_id=food_id,
                            notes="recommended",
                        )
                    )
            for food_id in excluded_ids:
                if food_id in valid_ids:
                    db.session.add(
                        RuleFoodMapTable(
                            diet_rule_id=rule.id,
                            food_id=food_id,
                            notes="avoid",
                        )
                    )
            db.session.commit()
        return jsonify(
            {
                "success": True,
                "rule": {
                    "id": rule.id,
                    "name": rule.rule_name,
                    "category": meta["category"],
                    "priority": meta["priority"],
                    "active": meta["active"],
                    "conditions": meta["conditions"],
                    "actions": [],
                    "description": rule.description or "",
                },
            }
        )
    except Exception:
        current_app.logger.exception("Failed to create diet rule")
        return jsonify({"success": False, "message": "Failed to create rule"}), 500


@dashboard_bp.route("/doctor/rules/<int:rule_id>", methods=["PATCH", "PUT", "DELETE"])
@login_required
@doctor_required
@csrf.exempt
def update_or_delete_doctor_rule(rule_id: int):
    if request.method == "DELETE":
        if not current_user.has_permission("rule.delete"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You have no permission to delete rules.",
                    }
                ),
                403,
            )
    else:
        if not current_user.has_permission("rule.edit"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You have no permission to edit rules.",
                    }
                ),
                403,
            )
    rule = DietRulesTable.query.get(rule_id)
    if not rule:
        return jsonify({"success": False, "message": "Rule not found"}), 404

    if request.method == "DELETE":
        try:
            GoalsTable.query.filter(GoalsTable.diet_rule_id == rule.id).update(
                {"diet_rule_id": None}, synchronize_session=False
            )
            RuleFoodMapTable.query.filter_by(diet_rule_id=rule.id).delete(
                synchronize_session=False
            )
            db.session.delete(rule)
            db.session.commit()
            return jsonify({"success": True})
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to delete rule")
            return jsonify({"success": False, "message": "Failed to delete rule"}), 500

    payload = request.get_json(silent=True) or {}

    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "message": "Rule name is required"}), 400
        rule.rule_name = name

    if "description" in payload:
        rule.description = (payload.get("description") or "").strip()

    if "active" in payload:
        rule.is_active = bool(payload.get("active"))

    def to_int_list(values):
        if not isinstance(values, list):
            return []
        ids = []
        for item in values:
            try:
                ids.append(int(item))
            except Exception:
                continue
        return ids

    meta_keys = {
        "conditions",
        "actions",
        "recommended_food_ids",
        "excluded_food_ids",
        "category",
        "priority",
    }
    update_meta = any(key in payload for key in meta_keys)
    recommended_ids = None
    excluded_ids = None
    meta_conditions = None

    if update_meta:
        meta = {}
        if rule.conditions:
            try:
                parsed = json.loads(rule.conditions)
                if isinstance(parsed, dict):
                    meta.update(parsed)
            except Exception:
                meta = {}

        if "conditions" in payload:
            conditions = payload.get("conditions") or []
            if not isinstance(conditions, list):
                conditions = [str(conditions)]
            meta["conditions"] = conditions

        if "actions" in payload:
            actions = payload.get("actions") or []
            if not isinstance(actions, list):
                actions = [str(actions)]
            meta["actions"] = actions

        if "category" in payload:
            meta["category"] = payload.get("category") or meta.get("category") or "diet"

        if "priority" in payload:
            meta["priority"] = (
                payload.get("priority") or meta.get("priority") or "medium"
            )

        if "recommended_food_ids" in payload:
            recommended_ids = to_int_list(payload.get("recommended_food_ids"))
            meta["recommended_food_ids"] = recommended_ids

        if "excluded_food_ids" in payload:
            excluded_ids = to_int_list(payload.get("excluded_food_ids"))
            meta["excluded_food_ids"] = excluded_ids

        rule.conditions = json.dumps(meta)
        meta_conditions = meta.get("conditions") or []

    if recommended_ids is not None or excluded_ids is not None:
        if recommended_ids is None:
            recommended_ids = []
        if excluded_ids is None:
            excluded_ids = []
        RuleFoodMapTable.query.filter_by(diet_rule_id=rule.id).delete(
            synchronize_session=False
        )
        valid_ids = {
            food.id
            for food in FoodsTable.query.filter(
                FoodsTable.id.in_(set(recommended_ids + excluded_ids))
            ).all()
        }
        for food_id in recommended_ids:
            if food_id in valid_ids:
                db.session.add(
                    RuleFoodMapTable(
                        diet_rule_id=rule.id,
                        food_id=food_id,
                        notes="recommended",
                    )
                )
        for food_id in excluded_ids:
            if food_id in valid_ids:
                db.session.add(
                    RuleFoodMapTable(
                        diet_rule_id=rule.id,
                        food_id=food_id,
                        notes="avoid",
                    )
                )

    if update_meta or "name" in payload or "goal_type" in payload:
        if meta_conditions is None:
            try:
                meta_conditions = DashboardService._parse_rule_meta(rule).get(
                    "conditions", []
                )
            except Exception:
                meta_conditions = []
        goal_type = (payload.get("goal_type") or "").strip().lower()
        goal_label = None
        if goal_type in {"lose", "gain", "maintain"}:
            goal_label = {
                "lose": "Lose Weight",
                "gain": "Gain Weight",
                "maintain": "Maintain Weight",
            }.get(goal_type)
        if not goal_label and not rule.goals:
            goal_label = DashboardService._infer_goal_label(
                rule.rule_name, meta_conditions, {}
            )
        goal = DashboardService._get_or_create_goal(goal_label)
        if goal:
            GoalsTable.query.filter(GoalsTable.diet_rule_id == rule.id).update(
                {"diet_rule_id": None}, synchronize_session=False
            )
            rule.goals = [goal]
            goal.diet_rule_id = rule.id

    try:
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "rule": {
                    "id": rule.id,
                    "name": rule.rule_name,
                    "active": rule.is_active,
                },
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update rule")
        return jsonify({"success": False, "message": "Failed to update rule"}), 500


@dashboard_bp.route("/doctor/consultation/new")
@login_required
@doctor_required
def new_consultation():
    """Start new consultation"""
    # Return consultation form data
    return jsonify(
        {
            "consultation_id": "CONS_" + str(datetime.utcnow().timestamp()),
            "patient": {
                "name": "Sample Patient",
                "age": 45,
                "gender": "Female",
                "history": "Type 2 Diabetes, Hypertension",
            },
            "symptoms": [
                {
                    "id": 1,
                    "name": "Increased thirst",
                    "description": "Feeling thirsty more often than usual",
                },
                {
                    "id": 2,
                    "name": "Frequent urination",
                    "description": "Needing to urinate more frequently",
                },
                {
                    "id": 3,
                    "name": "Fatigue",
                    "description": "Feeling tired and lacking energy",
                },
            ],
        }
    )


@dashboard_bp.route("/doctor/diagnosis/interface")
@login_required
@doctor_required
def diagnosis_interface():
    """Get diagnosis interface data"""
    symptoms = [
        {
            "id": 1,
            "name": "Increased thirst",
            "description": "Feeling thirsty more often than usual",
        },
        {
            "id": 2,
            "name": "Frequent urination",
            "description": "Needing to urinate more frequently",
        },
        {"id": 3, "name": "Fatigue", "description": "Feeling tired and lacking energy"},
        {
            "id": 4,
            "name": "Blurred vision",
            "description": "Vision appears blurry or unfocused",
        },
        {"id": 5, "name": "Weight loss", "description": "Unintentional weight loss"},
    ]

    return jsonify(
        {
            "patient": {
                "name": "Sample Patient",
                "age": 45,
                "gender": "Female",
                "history": "Type 2 Diabetes, Hypertension",
            },
            "symptoms": symptoms,
        }
    )


# User Dashboard Routes
@dashboard_bp.route("/user")
@login_required
@user_required
@permission_required(
    "user.dashboard.read", "You have no permission to access the user dashboard."
)
def user_dashboard():
    """User dashboard home page"""
    user_stats = DashboardService.get_user_statistics(current_user.id)
    candidate_results = (
        UserResultsTable.query.filter_by(user_id=current_user.id)
        .filter(UserResultsTable.result_data.isnot(None))
        .order_by(UserResultsTable.generated_at.desc())
        .limit(25)
        .all()
    )
    plan_total = 0
    all_results = (
        UserResultsTable.query.filter_by(user_id=current_user.id)
        .filter(UserResultsTable.result_data.isnot(None))
        .all()
    )
    for result in all_results:
        if not result.result_data:
            continue
        try:
            payload = json.loads(result.result_data)
        except Exception:
            continue
        if isinstance(payload, dict) and (payload.get("plan") or payload.get("metrics")):
            plan_total += 1

    def format_allergies(values):
        if not values:
            return "None"
        if not isinstance(values, list):
            values = [values]
        cleaned = []
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            cleaned.append(text.replace("_", " ").title())
        return ", ".join(cleaned) if cleaned else "None"

    plan_history = []
    for result in candidate_results:
        payload = {}
        if result.result_data:
            try:
                payload = json.loads(result.result_data)
            except Exception:
                payload = {}
        if not isinstance(payload, dict) or not (payload.get("plan") or payload.get("metrics")):
            continue

        metrics = payload.get("metrics") or payload.get("plan", {}).get("metrics") or {}
        profile = payload.get("plan", {}).get("profile") or {}
        form_data = payload.get("form_data") or {}
        health = form_data.get("health") or {}
        preferences = form_data.get("preferences") or {}
        allergies = profile.get("allergies") or health.get("allergies") or []

        plan_history.append(
            {
                "id": result.id,
                "generated_at": result.generated_at or result.created_at,
                "bmi": metrics.get("bmi") or result.bmi,
                "calories": metrics.get("calories"),
                "protein": metrics.get("protein"),
                "carbs": metrics.get("carbs"),
                "fat": metrics.get("fat"),
                "diet_type": profile.get("diet_type") or health.get("dietType"),
                "meals_per_day": profile.get("meals_per_day")
                or preferences.get("mealsPerDay"),
                "allergies": format_allergies(allergies),
            }
        )
        if len(plan_history) >= 8:
            break

    return render_template(
        "dashboard/user_dashboard.html",
        user=current_user,
        user_stats=user_stats,
        plan_history=plan_history,
        plan_total=plan_total,
    )


@dashboard_bp.route("/user/profile")
@login_required
@user_required
@permission_required(
    "user.dashboard.read", "You have no permission to view your profile."
)
def user_profile():
    """User profile page."""
    derived_goal = None
    rule_goals = []
    recent_results = (
        UserResultsTable.query.filter_by(user_id=current_user.id)
        .filter(UserResultsTable.result_data.isnot(None))
        .order_by(UserResultsTable.generated_at.desc())
        .limit(25)
        .all()
    )
    for result in recent_results:
        if not result.result_data:
            continue
        try:
            payload = json.loads(result.result_data)
        except Exception:
            continue
        if not isinstance(payload, dict) or not (payload.get("plan") or payload.get("metrics")):
            continue
        try:
            plan = payload.get("plan") or {}
            rule = plan.get("rule") or {}
            rule_id = rule.get("id")
            if rule_id:
                rule_goals = (
                    GoalsTable.query.filter_by(diet_rule_id=rule_id)
                    .order_by(GoalsTable.name.asc())
                    .all()
                )
            derived_goal = DashboardService._infer_goal_label(
                rule.get("name"),
                rule.get("conditions") or [],
                plan.get("profile") or {},
            )
            break
        except Exception:
            current_app.logger.exception("Failed to derive goal from latest plan")

    return render_template(
        "dashboard/user_profile.html",
        user=current_user,
        derived_goal=derived_goal,
        rule_goals=rule_goals,
    )


@dashboard_bp.route("/user/profile/edit", methods=["GET", "POST"])
@login_required
@user_required
@permission_required(
    "user.dashboard.update", "You have no permission to update your profile."
)
def user_profile_edit():
    """Edit user profile info."""
    form = UserProfileEditForm(current_user, obj=current_user)

    if form.validate_on_submit():
        current_user.username = (form.username.data or "").strip()
        current_user.full_name = (form.full_name.data or "").strip()

        photo_file = form.photo.data
        if photo_file and getattr(photo_file, "filename", ""):
            filename = secure_filename(photo_file.filename)
            _, ext = os.path.splitext(filename)
            safe_ext = ext.lower() if ext else ""
            unique_name = f"user_{current_user.id}_{uuid.uuid4().hex}{safe_ext}"
            project_root = os.path.dirname(current_app.root_path)
            upload_dir = os.path.join(project_root, "images", "profiles")
            os.makedirs(upload_dir, exist_ok=True)
            photo_file.save(os.path.join(upload_dir, unique_name))
            current_user.photo = f"images/profiles/{unique_name}"

        try:
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("dashboard.user_profile"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to update user profile")
            flash("Failed to update profile. Please try again.", "danger")

    return render_template(
        "dashboard/user_profile_edit.html",
        user=current_user,
        form=form,
    )


@dashboard_bp.route("/user/diet-expert")
@login_required
@user_required
@permission_required(
    "user.dashboard.create", "You have no permission to generate diet plans."
)
def user_diet_expert():
    """Diet expert system page for users."""
    return render_template("dashboard/user_diet_expert.html")


@dashboard_bp.route("/user/data")
@login_required
@user_required
@permission_required(
    "user.dashboard.read",
    "You have no permission to access dashboard data.",
    json_response=True,
)
def user_dashboard_data():
    """User dashboard data API endpoint"""
    stats = DashboardService.get_user_statistics(current_user.id)
    user_results = (
        UserResultsTable.query.filter_by(user_id=current_user.id)
        .order_by(UserResultsTable.created_at.desc())
        .limit(10)
        .all()
    )
    diagnoses = []
    for result in user_results:
        if not result.result_data:
            continue
        try:
            payload = json.loads(result.result_data)
        except Exception:
            continue
        diagnosis_data = None
        if isinstance(payload, dict):
            if payload.get("type") == "diagnosis":
                diagnosis_data = payload.get("diagnosis")
            elif "diagnosis" in payload:
                diagnosis_data = payload.get("diagnosis")
        if not isinstance(diagnosis_data, dict):
            continue
        primary = diagnosis_data.get("primary_diagnosis", {}) or {}
        condition = primary.get("name", "Diagnosis")
        confidence = primary.get("confidence")
        diagnoses.append(
            {
                "timestamp": result.created_at.isoformat(),
                "condition": condition,
                "confidence": confidence,
            }
        )

    return jsonify(
        {
            "user_bmi": stats.get("user_bmi"),
            "active_goals": stats.get("active_goals"),
            "total_diagnoses": stats.get("total_diagnoses"),
            "upcoming_appointments": stats.get("upcoming_appointments"),
            "diagnoses": diagnoses,
        }
    )


@dashboard_bp.route("/user/submit", methods=["POST"])
@login_required
@user_required
@csrf.exempt
@permission_required(
    "user.dashboard.create",
    "You have no permission to submit dashboard data.",
    json_response=True,
)
def user_dashboard_submit():
    payload = request.get_json(silent=True) or {}
    try:
        result = DashboardService.save_user_dashboard_submission(
            current_user.id, payload
        )
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        current_app.logger.exception("Failed to save dashboard submission")
        return jsonify({"success": False, "message": "Failed to save submission"}), 500


@dashboard_bp.route("/user/symptoms")
@login_required
@user_required
@permission_required("user.dashboard.read", "You have no permission to view symptoms.")
def get_symptoms():
    """Get available symptoms for user selection"""
    symptoms = [
        {
            "id": 1,
            "name": "Increased thirst",
            "description": "Feeling thirsty more often than usual",
        },
        {
            "id": 2,
            "name": "Frequent urination",
            "description": "Needing to urinate more frequently",
        },
        {"id": 3, "name": "Fatigue", "description": "Feeling tired and lacking energy"},
        {
            "id": 4,
            "name": "Blurred vision",
            "description": "Vision appears blurry or unfocused",
        },
        {
            "id": 5,
            "name": "Unexplained weight loss",
            "description": "Losing weight without trying",
        },
        {
            "id": 6,
            "name": "Increased hunger",
            "description": "Feeling hungry more often than usual",
        },
        {
            "id": 7,
            "name": "Slow-healing sores",
            "description": "Cuts or sores that heal slowly",
        },
        {
            "id": 8,
            "name": "Frequent infections",
            "description": "Getting sick more often than usual",
        },
    ]

    return jsonify({"symptoms": symptoms})


@dashboard_bp.route("/user/diagnosis", methods=["POST"])
@login_required
@user_required
@permission_required(
    "user.dashboard.create",
    "You have no permission to run a diagnosis.",
    json_response=True,
)
def run_diagnosis():
    """Run diagnosis based on selected symptoms"""
    data = request.get_json()
    symptoms = data.get("symptoms", [])

    # Simplified diagnosis logic
    # In a real implementation, this would use the inference engine

    # Mock diagnosis results based on symptoms
    primary_diagnosis = {
        "name": "Type 2 Diabetes Risk",
        "description": "Based on your symptoms, you may be at risk for Type 2 Diabetes",
        "confidence": 75,
    }

    recommendations = [
        "Consult with a healthcare professional for proper diagnosis",
        "Monitor your blood sugar levels regularly",
        "Maintain a healthy diet low in refined sugars",
        "Engage in regular physical activity",
        "Stay hydrated and get adequate sleep",
    ]

    next_steps = [
        "Schedule an appointment with your doctor",
        "Keep a symptom diary",
        "Research diabetes management strategies",
        "Consider dietary changes",
    ]

    result_payload = {
        "type": "diagnosis",
        "diagnosis": {
            "symptoms": symptoms,
            "primary_diagnosis": primary_diagnosis,
            "recommendations": recommendations,
            "next_steps": next_steps,
        },
    }

    # Save diagnosis result
    user_result = UserResultsTable(
        user_id=current_user.id,
        status="completed",
        result_data=json.dumps(result_payload),
        created_at=datetime.utcnow(),
    )
    db.session.add(user_result)
    db.session.commit()

    return jsonify(
        {
            "primary_diagnosis": primary_diagnosis,
            "recommendations": recommendations,
            "next_steps": next_steps,
            "result_id": user_result.id,
        }
    )


# Shared Routes
@dashboard_bp.route("/")
@login_required
def dashboard_home():
    """Redirect to appropriate dashboard based on user role"""
    if current_user.has_role("admin"):
        return redirect(url_for("dashboard.admin_dashboard"))
    elif current_user.has_role("doctor"):
        return redirect(url_for("dashboard.doctor_dashboard"))
    else:
        return redirect(url_for("dashboard.user_dashboard"))


# Error handlers
@dashboard_bp.errorhandler(403)
def forbidden(e):
    flash("You do not have permission to access this page.", "danger")
    return redirect(url_for("auth.login"))


@dashboard_bp.errorhandler(404)
def not_found(e):
    flash("Page not found.", "warning")
    return redirect(url_for("main.home"))
