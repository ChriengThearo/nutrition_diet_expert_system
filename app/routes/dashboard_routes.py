from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for,
    current_app,
    session,
)
from flask_login import login_required, current_user
from functools import wraps
from app.models.user import UserTable
from app.models.role import RoleTable
from app.models.goal import GoalsTable
from app.models.diet_rule import DietRulesTable
from app.models.food import FoodsTable
from app.models.cooked_food import CookedFoodsTable
from app.models.food_group import FoodGroupTable
from app.models.rule_food_map import RuleFoodMapTable
from app.models.user_result import UserResultsTable
from app.forms.dashboard_forms import UserProfileEditForm
from app.services.dashboard_services import DashboardService
from app.services.diet_rule_service import DietRuleService
from app.routes.access_control import permission_required
from extensions import db, csrf
from datetime import datetime, timedelta
from sqlalchemy.orm import selectinload
import json
import os
import re
import uuid
from werkzeug.utils import secure_filename

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _is_khmer_ui():
    return str(session.get("ui_lang", "km")).strip().lower() != "en"


def _normalize_text(value):
    return str(value or "").strip()


def _localize_goal_name(value):
    text = _normalize_text(value)
    if not text:
        return "មិនទាន់ជ្រើសរើស"

    token = text.lower().replace("-", " ").replace("_", " ")
    token = " ".join(token.split())

    if any(
        key in token
        for key in (
            "maintain weight",
            "maintenance weight",
            "weight maintenance",
            "maintenance",
            "maintain",
            "balance weight",
        )
    ):
        return "រក្សាទម្ងន់"

    if any(
        key in token
        for key in (
            "lose weight",
            "weight loss",
            "reduce weight",
            "fat loss",
            "slim",
        )
    ):
        return "បញ្ចុះទម្ងន់"

    if any(
        key in token
        for key in (
            "gain muscle",
            "muscle gain",
            "build muscle",
            "muscle",
        )
    ):
        return "បង្កើនសាច់ដុំ"

    if any(key in token for key in ("gain weight", "weight gain")):
        return "បង្កើនទម្ងន់"

    if any(
        key in token
        for key in (
            "blood sugar",
            "diabetes control",
            "diabetes management",
            "glucose control",
            "prediabetes",
            "diabetes",
        )
    ):
        return "គ្រប់គ្រងជាតិស្ករក្នុងឈាម"

    if any(key in token for key in ("improve health", "health improvement")):
        return "លើកកម្ពស់សុខភាព"

    if any(key in token for key in ("athletic performance", "sport performance")):
        return "បង្កើនសមត្ថភាពកីឡា"

    if "detox" in token:
        return "បន្សាបជាតិពុល"

    return text


def _localize_diet_type(value):
    text = _normalize_text(value)
    if not text:
        return "មិនទាន់កំណត់"

    token = text.lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "normal": "ធម្មតា",
        "vegan": "វីហ្គាន់",
        "vegetarian": "បួស",
        "keto": "គីតូ",
        "low_carb": "កាបូអ៊ីដ្រាតទាប",
        "mediterranean": "មេឌីទែរ៉ាណេ",
        "high_protein": "ប្រូតេអ៊ីនខ្ពស់",
        "paleo": "ផាលេអូ",
        "pescatarian": "បួសត្រី",
    }
    return mapping.get(token, text)


def _localize_allergy_name(value):
    text = _normalize_text(value)
    if not text:
        return ""

    token = text.lower().replace("-", "_").replace(" ", "_")
    if token in {"none", "no_allergy", "no_allergies", "na", "n_a"}:
        return ""
    mapping = {
        "seafood": "អាហារសមុទ្រ",
        "shellfish": "សត្វសំបក",
        "shrimp": "បង្គា",
        "crab": "ក្តាម",
        "lobster": "បង្កងសមុទ្រ",
        "fish": "ត្រី",
        "egg": "ស៊ុត",
        "eggs": "ស៊ុត",
        "soy": "សណ្ដែកសៀង",
        "soya": "សណ្ដែកសៀង",
        "soybean": "សណ្ដែកសៀង",
        "milk": "ទឹកដោះគោ",
        "dairy": "ផលិតផលទឹកដោះគោ",
        "lactose": "ឡាក់តូស",
        "peanut": "សណ្តែកដី",
        "peanuts": "សណ្តែកដី",
        "nut": "គ្រាប់ធញ្ញជាតិ",
        "nuts": "គ្រាប់ធញ្ញជាតិ",
        "almond": "អាល់ម៉ុន",
        "cashew": "ស្វាយចន្ទី",
        "walnut": "គ្រាប់វ៉ាល់ណាត់",
        "gluten": "ក្លុយតែន",
        "wheat": "ស្រូវសាលី",
        "sesame": "ល្ង",
        "mustard": "មូស្តាដ",
    }
    return mapping.get(token, text)


def _localize_allergies(values):
    if not values:
        return "មិនមាន"

    if isinstance(values, (list, tuple, set)):
        raw_items = list(values)
    else:
        text = _normalize_text(values)
        if not text:
            return "មិនមាន"
        text = re.sub(r"\band\b", ",", text, flags=re.IGNORECASE)
        raw_items = re.split(r"[;,/|]+", text)

    labels = []
    seen = set()
    for item in raw_items:
        label = _localize_allergy_name(item)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)

    return ", ".join(labels) if labels else "មិនមាន"


def _to_int_list(values):
    if not isinstance(values, list):
        return []
    ids = []
    for item in values:
        try:
            ids.append(int(item))
        except Exception:
            continue
    return ids


def _normalize_rule_food_groups(payload):
    raw_groups = payload.get("food_groups")
    normalized = []

    if isinstance(raw_groups, list):
        for index, item in enumerate(raw_groups):
            group = item if isinstance(item, dict) else {}
            group_key = str(group.get("group_key") or "").strip() or f"group_{index + 1}"
            normalized.append(
                {
                    "group_key": group_key,
                    "recommended_food_ids": _to_int_list(
                        group.get("recommended_food_ids")
                    ),
                    "excluded_food_ids": _to_int_list(group.get("excluded_food_ids")),
                    "recommended_cooked_food_ids": _to_int_list(
                        group.get("recommended_cooked_food_ids")
                    ),
                    "excluded_cooked_food_ids": _to_int_list(
                        group.get("excluded_cooked_food_ids")
                    ),
                }
            )

    if not normalized:
        normalized.append(
            {
                "group_key": "group_1",
                "recommended_food_ids": _to_int_list(payload.get("recommended_food_ids")),
                "excluded_food_ids": _to_int_list(payload.get("excluded_food_ids")),
                "recommended_cooked_food_ids": _to_int_list(
                    payload.get("recommended_cooked_food_ids")
                ),
                "excluded_cooked_food_ids": _to_int_list(
                    payload.get("excluded_cooked_food_ids")
                ),
            }
        )

    return normalized


def _flatten_group_ids(groups, field_name):
    values = []
    for group in groups or []:
        items = group.get(field_name) if isinstance(group, dict) else []
        if not isinstance(items, list):
            continue
        for item in items:
            try:
                values.append(int(item))
            except Exception:
                continue
    seen = set()
    flattened = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        flattened.append(value)
    return flattened


def _build_rule_food_groups(rule):
    grouped = {}
    try:
        food_groups = sorted(rule.food_groups or [], key=lambda item: item.id or 0)
    except Exception:
        return []
    for food_group in food_groups:
        mapping = food_group.rule_food_map
        if not mapping:
            continue

        group_key = str(food_group.group_key or "").strip() or "group_1"
        if group_key not in grouped:
            grouped[group_key] = {
                "group_key": group_key,
                "recommended_food_ids": [],
                "excluded_food_ids": [],
                "recommended_cooked_food_ids": [],
                "excluded_cooked_food_ids": [],
            }

        target = grouped[group_key]
        is_avoid = (mapping.notes or "").strip().lower() == "avoid"
        if mapping.food_id is not None:
            key = "excluded_food_ids" if is_avoid else "recommended_food_ids"
            target[key].append(int(mapping.food_id))
        if mapping.cooked_food_id is not None:
            key = (
                "excluded_cooked_food_ids"
                if is_avoid
                else "recommended_cooked_food_ids"
            )
            target[key].append(int(mapping.cooked_food_id))

    return list(grouped.values())


def _replace_rule_food_groups(rule_id, food_groups):
    existing_groups = FoodGroupTable.query.filter_by(diet_rule_id=rule_id).all()
    existing_map_ids = [item.rule_food_map_id for item in existing_groups if item.rule_food_map_id]

    if existing_groups:
        FoodGroupTable.query.filter_by(diet_rule_id=rule_id).delete(
            synchronize_session=False
        )
    if existing_map_ids:
        RuleFoodMapTable.query.filter(
            RuleFoodMapTable.id.in_(set(existing_map_ids))
        ).delete(synchronize_session=False)

    all_food_ids = set(_flatten_group_ids(food_groups, "recommended_food_ids"))
    all_food_ids.update(_flatten_group_ids(food_groups, "excluded_food_ids"))
    all_cooked_food_ids = set(
        _flatten_group_ids(food_groups, "recommended_cooked_food_ids")
    )
    all_cooked_food_ids.update(_flatten_group_ids(food_groups, "excluded_cooked_food_ids"))

    valid_food_ids = {
        food.id
        for food in FoodsTable.query.filter(FoodsTable.id.in_(all_food_ids)).all()
    }
    valid_cooked_food_ids = {
        cooked_food.id
        for cooked_food in CookedFoodsTable.query.filter(
            CookedFoodsTable.id.in_(all_cooked_food_ids)
        ).all()
    }

    def attach_mapping(group_key, food_id=None, cooked_food_id=None, notes="recommended"):
        mapping = RuleFoodMapTable(
            food_id=food_id,
            cooked_food_id=cooked_food_id,
            notes=notes,
        )
        db.session.add(mapping)
        db.session.flush()
        db.session.add(
            FoodGroupTable(
                diet_rule_id=rule_id,
                rule_food_map_id=mapping.id,
                group_key=group_key,
            )
        )

    for index, group in enumerate(food_groups or []):
        if not isinstance(group, dict):
            continue
        group_key = str(group.get("group_key") or "").strip() or f"group_{index + 1}"
        for food_id in _to_int_list(group.get("recommended_food_ids")):
            if food_id in valid_food_ids:
                attach_mapping(group_key, food_id=food_id, notes="recommended")
        for food_id in _to_int_list(group.get("excluded_food_ids")):
            if food_id in valid_food_ids:
                attach_mapping(group_key, food_id=food_id, notes="avoid")
        for cooked_food_id in _to_int_list(group.get("recommended_cooked_food_ids")):
            if cooked_food_id in valid_cooked_food_ids:
                attach_mapping(
                    group_key, cooked_food_id=cooked_food_id, notes="recommended"
                )
        for cooked_food_id in _to_int_list(group.get("excluded_cooked_food_ids")):
            if cooked_food_id in valid_cooked_food_ids:
                attach_mapping(group_key, cooked_food_id=cooked_food_id, notes="avoid")


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
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)
    page = page if isinstance(page, int) and page > 0 else 1
    per_page = per_page if isinstance(per_page, int) and per_page > 0 else 20
    per_page = min(per_page, 100)

    total_rules = DietRulesTable.query.count()
    total_pages = (total_rules + per_page - 1) // per_page if total_rules else 0
    offset = (page - 1) * per_page

    rules = (
        DietRulesTable.query.options(
            selectinload(DietRulesTable.goals),
            selectinload(DietRulesTable.food_groups).selectinload(
                FoodGroupTable.rule_food_map
            ),
        )
        .order_by(DietRulesTable.rule_name.asc(), DietRulesTable.id.asc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    result = []

    for rule in rules:
        conditions = []
        category = "diet"
        priority = "medium"
        active = bool(getattr(rule, "is_active", True))
        actions = []
        recommended_ids = []
        excluded_ids = []
        recommended_cooked_ids = []
        excluded_cooked_ids = []
        food_groups = []

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
                    recommended_cooked_ids = (
                        parsed.get("recommended_cooked_food_ids") or []
                    )
                    excluded_cooked_ids = parsed.get("excluded_cooked_food_ids") or []
                    food_groups = parsed.get("food_groups") or []
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

        db_food_groups = _build_rule_food_groups(rule)
        if db_food_groups:
            food_groups = db_food_groups
            recommended_ids = _flatten_group_ids(food_groups, "recommended_food_ids")
            excluded_ids = _flatten_group_ids(food_groups, "excluded_food_ids")
            recommended_cooked_ids = _flatten_group_ids(
                food_groups, "recommended_cooked_food_ids"
            )
            excluded_cooked_ids = _flatten_group_ids(
                food_groups, "excluded_cooked_food_ids"
            )
        elif isinstance(food_groups, list) and food_groups:
            normalized_meta_groups = _normalize_rule_food_groups(
                {"food_groups": food_groups}
            )
            food_groups = normalized_meta_groups
            recommended_ids = _flatten_group_ids(food_groups, "recommended_food_ids")
            excluded_ids = _flatten_group_ids(food_groups, "excluded_food_ids")
            recommended_cooked_ids = _flatten_group_ids(
                food_groups, "recommended_cooked_food_ids"
            )
            excluded_cooked_ids = _flatten_group_ids(
                food_groups, "excluded_cooked_food_ids"
            )
        else:
            food_groups = _normalize_rule_food_groups(
                {
                    "recommended_food_ids": recommended_ids,
                    "excluded_food_ids": excluded_ids,
                    "recommended_cooked_food_ids": recommended_cooked_ids,
                    "excluded_cooked_food_ids": excluded_cooked_ids,
                }
            )

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
                "recommended_cooked_food_ids": recommended_cooked_ids,
                "excluded_cooked_food_ids": excluded_cooked_ids,
                "food_groups": food_groups,
            }
        )

    return jsonify(
        {
            "rules": result,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_rules,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    )


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
                    "sugar": food.sugar,
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
        sugar=to_float(get_value("sugar")),
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
                    "sugar": food.sugar,
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
            mapping_rows = RuleFoodMapTable.query.filter_by(food_id=food.id).all()
            mapping_ids = [row.id for row in mapping_rows]
            if mapping_ids:
                FoodGroupTable.query.filter(
                    FoodGroupTable.rule_food_map_id.in_(set(mapping_ids))
                ).delete(synchronize_session=False)
                RuleFoodMapTable.query.filter(
                    RuleFoodMapTable.id.in_(set(mapping_ids))
                ).delete(synchronize_session=False)
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
    food.sugar = to_float(get_value("sugar"))
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
                    "sugar": food.sugar,
                    "fat": food.fat,
                },
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update food")
        return jsonify({"success": False, "message": "Failed to update food"}), 500


@dashboard_bp.route("/doctor/cooked-foods", methods=["GET"])
@login_required
@doctor_required
@permission_required(
    "food.read", "You have no permission to view cooked foods.", json_response=True
)
def doctor_cooked_foods():
    """Return cooked foods for doctor dashboard."""
    cooked_foods = (
        CookedFoodsTable.query.order_by(CookedFoodsTable.created_at.desc())
        .limit(100)
        .all()
    )
    return jsonify(
        {
            "cooked_foods": [
                {
                    "id": cooked_food.id,
                    "name": cooked_food.name,
                    "photo": cooked_food.photo,
                    "description": cooked_food.description or "",
                    "is_vegan": 1 if getattr(cooked_food, "is_gevan", False) else 0,
                    "food_type": getattr(cooked_food, "food_type", "cooked")
                    or "cooked",
                    "cooking_method": cooked_food.cooking_method or "",
                    "calories": cooked_food.calories,
                    "protein": cooked_food.protein,
                    "sugar": cooked_food.sugar,
                    "fat": cooked_food.fat,
                }
                for cooked_food in cooked_foods
            ]
        }
    )


@dashboard_bp.route("/doctor/cooked-foods", methods=["POST"])
@login_required
@doctor_required
@csrf.exempt
@permission_required(
    "food.create", "You have no permission to create cooked foods.", json_response=True
)
def create_doctor_cooked_food():
    payload = request.get_json(silent=True) or {}
    form_data = request.form or {}
    name = (payload.get("name") or form_data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Cooked food name is required"}), 400

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

    photo_path = None
    photo_file = request.files.get("photo")
    if photo_file and photo_file.filename:
        filename = secure_filename(photo_file.filename)
        _, ext = os.path.splitext(filename)
        safe_ext = ext if ext else ""
        unique_name = f"cooked_food_{uuid.uuid4().hex}{safe_ext}"
        project_root = os.path.dirname(current_app.root_path)
        upload_dir = os.path.join(project_root, "images", "cooked_foods")
        os.makedirs(upload_dir, exist_ok=True)
        photo_file.save(os.path.join(upload_dir, unique_name))
        photo_path = f"images/cooked_foods/{unique_name}"

    cooked_food = CookedFoodsTable(
        name=name,
        photo=photo_path or (get_value("photo") or "").strip() or None,
        description=(get_value("description") or "").strip(),
        food_type=(get_value("food_type") or "cooked").strip().lower() or "cooked",
        cooking_method=(get_value("cooking_method") or "").strip() or None,
        calories=to_float(get_value("calories")),
        protein=to_float(get_value("protein")),
        sugar=to_float(get_value("sugar")),
        fat=to_float(get_value("fat")),
    )
    vegan_value = to_bool(get_value("is_gevan"))
    if vegan_value is not None:
        cooked_food.is_gevan = vegan_value

    try:
        db.session.add(cooked_food)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "cooked_food": {
                    "id": cooked_food.id,
                    "name": cooked_food.name,
                    "photo": cooked_food.photo,
                    "description": cooked_food.description or "",
                    "food_type": cooked_food.food_type or "cooked",
                    "cooking_method": cooked_food.cooking_method or "",
                    "calories": cooked_food.calories,
                    "protein": cooked_food.protein,
                    "sugar": cooked_food.sugar,
                    "fat": cooked_food.fat,
                },
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to create cooked food")
        return jsonify({"success": False, "message": "Failed to create cooked food"}), 500


@dashboard_bp.route("/doctor/cooked-foods/<int:cooked_food_id>", methods=["POST", "DELETE"])
@login_required
@doctor_required
@csrf.exempt
def update_or_delete_doctor_cooked_food(cooked_food_id: int):
    if request.method == "DELETE":
        if not current_user.has_permission("food.delete"):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You have no permission to delete cooked food.",
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
                        "message": "You have no permission to edit cooked food.",
                    }
                ),
                403,
            )

    cooked_food = CookedFoodsTable.query.get(cooked_food_id)
    if not cooked_food:
        return jsonify({"success": False, "message": "Cooked food not found"}), 404

    if request.method == "DELETE":
        try:
            mapping_rows = RuleFoodMapTable.query.filter_by(
                cooked_food_id=cooked_food.id
            ).all()
            mapping_ids = [row.id for row in mapping_rows]
            if mapping_ids:
                FoodGroupTable.query.filter(
                    FoodGroupTable.rule_food_map_id.in_(set(mapping_ids))
                ).delete(synchronize_session=False)
                RuleFoodMapTable.query.filter(
                    RuleFoodMapTable.id.in_(set(mapping_ids))
                ).delete(synchronize_session=False)
            if cooked_food.photo:
                project_root = os.path.dirname(current_app.root_path)
                photo_path = os.path.join(project_root, cooked_food.photo)
                if os.path.isfile(photo_path):
                    os.remove(photo_path)
            db.session.delete(cooked_food)
            db.session.commit()
            return jsonify({"success": True})
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to delete cooked food")
            return (
                jsonify({"success": False, "message": "Failed to delete cooked food"}),
                500,
            )

    payload = request.get_json(silent=True) or {}
    form_data = request.form or {}
    name = (payload.get("name") or form_data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Cooked food name is required"}), 400

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
        unique_name = f"cooked_food_{uuid.uuid4().hex}{safe_ext}"
        project_root = os.path.dirname(current_app.root_path)
        upload_dir = os.path.join(project_root, "images", "cooked_foods")
        os.makedirs(upload_dir, exist_ok=True)
        photo_file.save(os.path.join(upload_dir, unique_name))
        cooked_food.photo = f"images/cooked_foods/{unique_name}"

    cooked_food.name = name
    cooked_food.description = (get_value("description") or "").strip()
    cooked_food.food_type = (get_value("food_type") or "cooked").strip().lower() or "cooked"
    cooked_food.cooking_method = (get_value("cooking_method") or "").strip() or None
    vegan_value = to_bool(get_value("is_gevan"))
    if vegan_value is not None:
        cooked_food.is_gevan = vegan_value
    cooked_food.calories = to_float(get_value("calories"))
    cooked_food.protein = to_float(get_value("protein"))
    cooked_food.sugar = to_float(get_value("sugar"))
    cooked_food.fat = to_float(get_value("fat"))

    try:
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "cooked_food": {
                    "id": cooked_food.id,
                    "name": cooked_food.name,
                    "photo": cooked_food.photo,
                    "description": cooked_food.description or "",
                    "food_type": cooked_food.food_type or "cooked",
                    "cooking_method": cooked_food.cooking_method or "",
                    "calories": cooked_food.calories,
                    "protein": cooked_food.protein,
                    "sugar": cooked_food.sugar,
                    "fat": cooked_food.fat,
                },
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update cooked food")
        return (
            jsonify({"success": False, "message": "Failed to update cooked food"}),
            500,
        )


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

        if form.new_password.data:
            current_user.set_password(form.new_password.data)

        try:
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("dashboard.doctor_profile"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to update doctor profile")
            flash("Failed to update profile. Please try again.", "danger")

    return render_template(
        "dashboard/doctor_profile_edit.html",
        user=current_user,
        form=form,
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
    food_groups = _normalize_rule_food_groups(payload)
    recommended_ids = _flatten_group_ids(food_groups, "recommended_food_ids")
    excluded_ids = _flatten_group_ids(food_groups, "excluded_food_ids")
    recommended_cooked_ids = _flatten_group_ids(
        food_groups, "recommended_cooked_food_ids"
    )
    excluded_cooked_ids = _flatten_group_ids(food_groups, "excluded_cooked_food_ids")

    active = bool(payload.get("active", True))
    meta = {
        "category": payload.get("category") or "health",
        "priority": payload.get("priority") or "medium",
        "active": active,
        "conditions": conditions,
        "actions": payload.get("actions") or [],
        "recommended_food_ids": recommended_ids,
        "excluded_food_ids": excluded_ids,
        "recommended_cooked_food_ids": recommended_cooked_ids,
        "excluded_cooked_food_ids": excluded_cooked_ids,
        "food_groups": food_groups,
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

        _replace_rule_food_groups(rule.id, food_groups)
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
                    "food_groups": food_groups,
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
            group_rows = FoodGroupTable.query.filter_by(diet_rule_id=rule.id).all()
            mapping_ids = [row.rule_food_map_id for row in group_rows if row.rule_food_map_id]
            if group_rows:
                FoodGroupTable.query.filter_by(diet_rule_id=rule.id).delete(
                    synchronize_session=False
                )
            if mapping_ids:
                RuleFoodMapTable.query.filter(
                    RuleFoodMapTable.id.in_(set(mapping_ids))
                ).delete(synchronize_session=False)
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

    meta_keys = {
        "conditions",
        "actions",
        "recommended_food_ids",
        "excluded_food_ids",
        "recommended_cooked_food_ids",
        "excluded_cooked_food_ids",
        "food_groups",
        "category",
        "priority",
    }
    update_meta = any(key in payload for key in meta_keys)
    meta_conditions = None
    normalized_food_groups = None

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
            meta["recommended_food_ids"] = _to_int_list(
                payload.get("recommended_food_ids")
            )

        if "excluded_food_ids" in payload:
            meta["excluded_food_ids"] = _to_int_list(payload.get("excluded_food_ids"))

        if "recommended_cooked_food_ids" in payload:
            meta["recommended_cooked_food_ids"] = _to_int_list(
                payload.get("recommended_cooked_food_ids")
            )

        if "excluded_cooked_food_ids" in payload:
            meta["excluded_cooked_food_ids"] = _to_int_list(
                payload.get("excluded_cooked_food_ids")
            )

        if (
            "food_groups" in payload
            or "recommended_food_ids" in payload
            or "excluded_food_ids" in payload
            or "recommended_cooked_food_ids" in payload
            or "excluded_cooked_food_ids" in payload
        ):
            normalized_food_groups = _normalize_rule_food_groups(payload)
            meta["food_groups"] = normalized_food_groups
            meta["recommended_food_ids"] = _flatten_group_ids(
                normalized_food_groups, "recommended_food_ids"
            )
            meta["excluded_food_ids"] = _flatten_group_ids(
                normalized_food_groups, "excluded_food_ids"
            )
            meta["recommended_cooked_food_ids"] = _flatten_group_ids(
                normalized_food_groups, "recommended_cooked_food_ids"
            )
            meta["excluded_cooked_food_ids"] = _flatten_group_ids(
                normalized_food_groups, "excluded_cooked_food_ids"
            )

        rule.conditions = json.dumps(meta)
        meta_conditions = meta.get("conditions") or []

    if normalized_food_groups is not None:
        _replace_rule_food_groups(rule.id, normalized_food_groups)

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
    "user.dashboard.read", "អ្នកមិនមានសិទ្ធិចូលប្រើផ្ទាំងគ្រប់គ្រងអ្នកប្រើប្រាស់ទេ។"
)
def user_dashboard():
    """User dashboard home page"""
    guest_mode_enabled = bool(session.get("user_guest_mode"))
    guest_history_entries = (
        session.get("guest_plan_history", []) if guest_mode_enabled else []
    )
    if not isinstance(guest_history_entries, list):
        guest_history_entries = []

    user_stats = (
        {} if guest_mode_enabled else DashboardService.get_user_statistics(current_user.id)
    )
    plan_total = 0

    def to_rounded_float(value, precision=1):
        try:
            if value in (None, ""):
                return None
            return round(float(value), precision)
        except Exception:
            return None

    def build_plan_signature(entry):
        if not isinstance(entry, dict):
            return ("invalid",)

        generated_at = entry.get("generated_at")
        if isinstance(generated_at, datetime):
            # Collapse to minute precision to absorb accidental duplicate submits.
            generated_key = generated_at.replace(second=0, microsecond=0).isoformat()
        else:
            generated_key = ""

        return (
            generated_key,
            to_rounded_float(entry.get("bmi"), precision=1),
            to_rounded_float(entry.get("calories"), precision=0),
            to_rounded_float(entry.get("protein"), precision=1),
            to_rounded_float(entry.get("sugar"), precision=1),
            to_rounded_float(entry.get("fat"), precision=1),
            to_rounded_float(entry.get("blood_sugar"), precision=1),
            str(entry.get("diet_type") or "").strip().lower(),
            str(entry.get("meals_per_day") or "").strip(),
            str(entry.get("allergies") or "").strip().lower(),
        )

    plan_history = []
    if not guest_mode_enabled:
        candidate_results = (
            UserResultsTable.query.filter_by(user_id=current_user.id)
            .filter(UserResultsTable.result_data.isnot(None))
            .order_by(UserResultsTable.generated_at.desc())
            .limit(25)
            .all()
        )
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
            if isinstance(payload, dict) and (
                payload.get("plan") or payload.get("metrics")
            ):
                plan_total += 1

        for result in candidate_results:
            payload = {}
            if result.result_data:
                try:
                    payload = json.loads(result.result_data)
                except Exception:
                    payload = {}
            if not isinstance(payload, dict) or not (
                payload.get("plan") or payload.get("metrics")
            ):
                continue

            metrics = payload.get("metrics") or payload.get("plan", {}).get("metrics") or {}
            profile = payload.get("plan", {}).get("profile") or {}
            form_data = payload.get("form_data") or {}
            health = form_data.get("health") or {}
            preferences = form_data.get("preferences") or {}
            allergies = profile.get("allergies") or health.get("allergies") or []
            diet_type_raw = profile.get("diet_type") or health.get("dietType")

            plan_history.append(
                {
                    "id": result.id,
                    "generated_at": result.generated_at or result.created_at,
                    "bmi": metrics.get("bmi") or result.bmi,
                    "calories": metrics.get("calories"),
                    "protein": metrics.get("protein"),
                    "sugar": metrics.get("sugar"),
                    "fat": metrics.get("fat"),
                    "blood_sugar": profile.get("blood_sugar")
                    if profile.get("blood_sugar") is not None
                    else health.get("blood_sugar"),
                    "diet_type": diet_type_raw,
                    "diet_type_label": _localize_diet_type(diet_type_raw),
                    "meals_per_day": profile.get("meals_per_day")
                    or preferences.get("mealsPerDay"),
                    "allergies": _localize_allergies(allergies),
                }
            )
            if len(plan_history) >= 8:
                break

    if guest_history_entries:
        guest_plan_history = []
        for entry in guest_history_entries:
            if not isinstance(entry, dict):
                continue
            generated_at = None
            raw_generated_at = entry.get("generated_at")
            if isinstance(raw_generated_at, str):
                try:
                    generated_at = datetime.fromisoformat(raw_generated_at)
                except Exception:
                    generated_at = None
            diet_type_raw = entry.get("diet_type")
            guest_plan_history.append(
                {
                    "id": entry.get("id") or f"guest-{uuid.uuid4().hex[:8]}",
                    "generated_at": generated_at,
                    "bmi": entry.get("bmi"),
                    "calories": entry.get("calories"),
                    "protein": entry.get("protein"),
                    "sugar": entry.get("sugar"),
                    "fat": entry.get("fat"),
                    "blood_sugar": entry.get("blood_sugar"),
                    "diet_type": diet_type_raw,
                    "diet_type_label": _localize_diet_type(diet_type_raw),
                    "meals_per_day": entry.get("meals_per_day"),
                    "allergies": _localize_allergies(entry.get("allergies")),
                }
            )

        if guest_plan_history:
            if guest_mode_enabled:
                plan_history = guest_plan_history[:8]
                plan_total = len(guest_plan_history)
            else:
                plan_history = guest_plan_history + plan_history
                plan_history.sort(
                    key=lambda item: item.get("generated_at") or datetime.min,
                    reverse=True,
                )
                plan_history = plan_history[:8]
                plan_total += len(guest_plan_history)

    if plan_history:
        deduped_plan_history = []
        seen_plan_signatures = set()
        for plan in plan_history:
            signature = build_plan_signature(plan)
            if signature in seen_plan_signatures:
                continue
            seen_plan_signatures.add(signature)
            deduped_plan_history.append(plan)
        plan_history = deduped_plan_history[:8]

    return render_template(
        "dashboard/user_dashboard.html",
        user=current_user,
        user_stats=user_stats,
        plan_history=plan_history,
        plan_total=plan_total,
        localized_user_goals=[_localize_goal_name(goal.name) for goal in current_user.goals],
        guest_mode=guest_mode_enabled,
    )


@dashboard_bp.route("/user/profile")
@login_required
@user_required
@permission_required(
    "user.dashboard.read", "អ្នកមិនមានសិទ្ធិមើលប្រវត្តិរូបរបស់អ្នកទេ។"
)
def user_profile():
    """User profile page."""
    guest_mode_enabled = bool(session.get("user_guest_mode"))
    if guest_mode_enabled:
        return render_template(
            "dashboard/user_profile.html",
            user=current_user,
            derived_goal=None,
            rule_goals=[],
            localized_user_goals=[],
            localized_rule_goals=[],
            localized_derived_goal=None,
            guest_mode=True,
        )

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

    localized_user_goals = [_localize_goal_name(goal.name) for goal in current_user.goals]
    localized_rule_goals = [_localize_goal_name(goal.name) for goal in rule_goals]
    localized_derived_goal = _localize_goal_name(derived_goal) if derived_goal else None

    return render_template(
        "dashboard/user_profile.html",
        user=current_user,
        derived_goal=derived_goal,
        rule_goals=rule_goals,
        localized_user_goals=localized_user_goals,
        localized_rule_goals=localized_rule_goals,
        localized_derived_goal=localized_derived_goal,
        guest_mode=False,
    )


@dashboard_bp.route("/user/profile/edit", methods=["GET", "POST"])
@login_required
@user_required
@permission_required(
    "user.dashboard.update", "អ្នកមិនមានសិទ្ធិកែប្រែប្រវត្តិរូបរបស់អ្នកទេ។"
)
def user_profile_edit():
    """Edit user profile info."""
    if session.get("user_guest_mode"):
        flash("សូមប្តូរទៅរបៀបអ្នកប្រើប្រាស់ ដើម្បីកែប្រវត្តិរូប។", "info")
        return redirect(url_for("dashboard.user_profile"))

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
            flash("បានធ្វើបច្ចុប្បន្នភាពប្រវត្តិរូបដោយជោគជ័យ។", "success")
            return redirect(url_for("dashboard.user_profile"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to update user profile")
            flash("មិនអាចធ្វើបច្ចុប្បន្នភាពប្រវត្តិរូបបានទេ។ សូមព្យាយាមម្តងទៀត។", "danger")

    return render_template(
        "dashboard/user_profile_edit.html",
        user=current_user,
        form=form,
    )


@dashboard_bp.route("/user/diet-expert")
@login_required
@user_required
@permission_required(
    "user.dashboard.create", "អ្នកមិនមានសិទ្ធិបង្កើតផែនការអាហារទេ។"
)
def user_diet_expert():
    """Diet expert system page for users."""
    last_form_data = None
    latest_result = (
        UserResultsTable.query.filter_by(user_id=current_user.id)
        .filter(UserResultsTable.result_data.isnot(None))
        .order_by(UserResultsTable.generated_at.desc())
        .first()
    )
    if latest_result and latest_result.result_data:
        try:
            payload = json.loads(latest_result.result_data)
            if isinstance(payload, dict) and payload.get("form_data"):
                last_form_data = payload["form_data"]
        except Exception:
            pass
    return render_template("dashboard/user_diet_expert.html", last_form_data=last_form_data)


@dashboard_bp.route("/user/ocr-upload", methods=["POST"])
@login_required
@user_required
@csrf.exempt
@permission_required(
    "user.dashboard.create",
    "អ្នកមិនមានសិទ្ធិនាំចូលឯកសារទេ។",
    json_response=True,
)
def user_ocr_upload():
    """Extract health data from an uploaded document using EasyOCR."""
    import tempfile

    uploaded = request.files.get("document")
    if not uploaded or not uploaded.filename:
        return jsonify({"success": False, "message": "មិនមានឯកសារត្រូវបានផ្ទុកឡើងទេ។"}), 400

    allowed_ext = {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "pdf"}
    ext = (
        uploaded.filename.rsplit(".", 1)[-1].lower()
        if "." in uploaded.filename
        else ""
    )
    if ext not in allowed_ext:
        return jsonify({"success": False, "message": "ប្រភេទឯកសារនេះមិនត្រូវបានគាំទ្រទេ។"}), 400

    tmp_path = None
    pdf_img_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
            uploaded.save(tmp)
            tmp_path = tmp.name

        # Convert PDF first page to image if needed
        image_path = tmp_path
        if ext == "pdf":
            try:
                from pdf2image import convert_from_path

                images = convert_from_path(tmp_path, first_page=1, last_page=1)
                if images:
                    pdf_img_path = tmp_path + ".png"
                    images[0].save(pdf_img_path, "PNG")
                    image_path = pdf_img_path
            except ImportError:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "ការគាំទ្រ PDF ត្រូវការ pdf2image។ សូមផ្ទុកឯកសាររូបភាពជំនួស។",
                        }
                    ),
                    400,
                )

        import easyocr

        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        results = reader.readtext(image_path)

        # Keep low-confidence tokens as well; small values like "F" can be weak.
        lines = [text for _, text, conf in results if conf > 0.05]

        full_text = "\n".join(lines)
        current_app.logger.info(
            "OCR extracted %d lines from uploaded document", len(lines)
        )

        extracted = _parse_health_document(full_text)
        if not extracted.get("gender"):
            extracted["gender"] = _extract_gender_from_ocr_layout(
                ocr_results=results,
                image_path=image_path,
                reader=reader,
            )
        extracted["raw_text"] = full_text

        return jsonify({"success": True, **extracted})
    except Exception as e:
        current_app.logger.exception("OCR processing failed")
        return (
            jsonify(
                {"success": False, "message": f"ការដំណើរការ OCR បរាជ័យ៖ {str(e)}"}
            ),
            500,
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if pdf_img_path:
            try:
                os.unlink(pdf_img_path)
            except OSError:
                pass


def _extract_gender_from_ocr_layout(ocr_results, image_path, reader):
    """Try to extract gender from layout-aware OCR when text-only parsing misses it."""
    import re

    try:
        from PIL import Image
        import numpy as np
    except Exception:
        return None

    if not ocr_results or not image_path or reader is None:
        return None

    def _normalize_gender_token(raw_value):
        if raw_value is None:
            return None

        cleaned = str(raw_value).strip().lower()
        if not cleaned:
            return None

        cleaned = cleaned.translate(
            str.maketrans(
                {
                    "0": "o",
                    "1": "l",
                    "|": "l",
                }
            )
        )
        cleaned = re.sub(r"[^a-z]", "", cleaned)

        if not cleaned:
            return None
        if cleaned in {"m", "male", "man", "boy"}:
            return "male"
        if cleaned in {"f", "female", "woman", "girl"}:
            return "female"
        if cleaned.startswith("mal"):
            return "male"
        if cleaned.startswith("fem"):
            return "female"
        if set(cleaned) == {"m"}:
            return "male"
        if set(cleaned) == {"f"}:
            return "female"
        return None

    def _bbox_stats(bbox):
        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        return {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "cx": (x_min + x_max) / 2,
            "cy": (y_min + y_max) / 2,
            "h": max(1.0, y_max - y_min),
        }

    entries = []
    for item in ocr_results:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        bbox, text, conf = item[0], item[1], item[2]
        token = str(text).strip()
        if not token:
            continue
        stats = _bbox_stats(bbox)
        entries.append(
            {
                "text": token,
                "conf": float(conf) if conf is not None else 0.0,
                **stats,
            }
        )

    if not entries:
        return None

    label_candidates = []
    for entry in entries:
        normalized = re.sub(r"[^a-z]", "", entry["text"].lower())
        if "gender" in normalized or normalized == "sex":
            label_candidates.append(entry)

    if not label_candidates:
        return None

    label = sorted(label_candidates, key=lambda item: item["conf"], reverse=True)[0]

    # Pass 1: same-row token from initial OCR.
    row_candidates = [
        entry
        for entry in entries
        if entry["cx"] > (label["x_max"] + 8)
        and abs(entry["cy"] - label["cy"]) <= max(20.0, label["h"] * 0.95)
    ]
    row_candidates.sort(key=lambda item: item["x_min"])
    row_genders = []
    for entry in row_candidates:
        for piece in re.split(r"[/|,\s:;\-]+", entry["text"]):
            normalized = _normalize_gender_token(piece)
            if normalized and normalized not in row_genders:
                row_genders.append(normalized)
    if len(row_genders) == 1:
        return row_genders[0]

    # Pass 2: targeted crop OCR around value cell.
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    width, height = image.size
    row_half_height = max(int(round(label["h"] * 1.8)), 48)
    y1 = max(0, int(round(label["cy"] - row_half_height)))
    y2 = min(height, int(round(label["cy"] + row_half_height)))

    value_column_candidates = [
        entry["x_min"]
        for entry in entries
        if entry["x_min"] > (label["x_max"] + 18)
        and abs(entry["cy"] - label["cy"]) <= 220
    ]
    if value_column_candidates:
        value_column_x = min(value_column_candidates)
    else:
        value_column_x = max(label["x_max"] + 26, width * 0.30)

    x1 = max(0, int(round(value_column_x - 75)))
    x2 = min(width, int(round(max(x1 + 220, value_column_x + max(165, width * 0.18)))))

    crop_windows = []
    if x2 > x1 and y2 > y1:
        crop_windows.append((x1, y1, x2, y2))
        crop_windows.append(
            (
                max(0, x1 - 45),
                max(0, y1 - 20),
                min(width, x2 + 70),
                min(height, y2 + 28),
            )
        )
    if not crop_windows:
        return None

    crop_passes = [
        {
            "min_size": 1,
            "text_threshold": 0.3,
            "low_text": 0.1,
            "contrast_ths": 0.05,
            "adjust_contrast": 0.8,
        },
        {
            "min_size": 1,
            "allowlist": "FfMmMalefemale",
            "text_threshold": 0.2,
            "low_text": 0.1,
        },
    ]

    for crop_box in crop_windows:
        crop_arr = np.array(image.crop(crop_box))
        for kwargs in crop_passes:
            try:
                crop_results = reader.readtext(crop_arr, **kwargs)
            except Exception:
                continue

            candidates = []
            for _, token, _ in crop_results:
                token = str(token).strip()
                if not token:
                    continue
                for piece in re.split(r"[/|,\s:;\-]+", token):
                    normalized = _normalize_gender_token(piece)
                    if normalized and normalized not in candidates:
                        candidates.append(normalized)

            if len(candidates) == 1:
                return candidates[0]

    return None


def _parse_health_document(text):
    """Parse OCR text from a health/medical document to extract form fields."""
    import re

    def _parse_ocr_number(raw_value):
        """Parse numeric tokens with common OCR mistakes (e.g. 2l0 -> 210)."""
        if raw_value is None:
            return None

        cleaned = str(raw_value).strip()
        if not cleaned:
            return None

        cleaned = cleaned.translate(
            str.maketrans(
                {
                    "o": "0",
                    "O": "0",
                    "l": "1",
                    "I": "1",
                    "|": "1",
                }
            )
        )
        cleaned = cleaned.replace(",", ".")
        cleaned = re.sub(r"[^0-9.]", "", cleaned)

        if cleaned.count(".") > 1:
            first_dot = cleaned.find(".")
            cleaned = cleaned[: first_dot + 1] + cleaned[first_dot + 1 :].replace(
                ".", ""
            )

        if not cleaned:
            return None

        try:
            value = float(cleaned)
        except (TypeError, ValueError):
            return None

        if value.is_integer():
            return int(value)
        return round(value, 2)

    def _normalize_gender_token(raw_value):
        """Normalize OCR gender tokens into 'male'/'female'."""
        if raw_value is None:
            return None

        cleaned = str(raw_value).strip().lower()
        if not cleaned:
            return None

        cleaned = cleaned.translate(
            str.maketrans(
                {
                    "0": "o",
                    "1": "l",
                    "|": "l",
                }
            )
        )
        cleaned = re.sub(r"[^a-z]", "", cleaned)

        if not cleaned:
            return None
        if cleaned in {"m", "male", "man", "boy"}:
            return "male"
        if cleaned in {"f", "female", "woman", "girl"}:
            return "female"
        if cleaned.startswith("mal"):
            return "male"
        if cleaned.startswith("fem"):
            return "female"
        if set(cleaned) == {"m"}:
            return "male"
        if set(cleaned) == {"f"}:
            return "female"
        return None

    result = {
        "age": None,
        "gender": None,
        "weight": None,
        "height": None,
        "blood_sugar": None,
        "allergies": [],
        "diet_type": None,
    }

    lower = text.lower()

    # --- Age ---
    for pattern in [
        r"age\s*[:\-]?\s*(\d{1,3})\s*(?:years|yrs|y\.?o\.?)?",
        r"(\d{1,3})\s*(?:years?\s*old|yrs?\s*old|y\.?o\.?)",
    ]:
        m = re.search(pattern, lower)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 120:
                result["age"] = val
                break

    # --- Gender ---
    # Prefer explicit "Sex/Gender" labels first; avoid broad global matches.
    lines = [line.strip().lower() for line in re.split(r"[\r\n]+", text) if line.strip()]
    for idx, line in enumerate(lines):
        if "sex" not in line and "gender" not in line:
            continue

        contexts = [line]
        if idx + 1 < len(lines):
            contexts.append(f"{line} {lines[idx + 1]}")

        for context in contexts:
            m = re.search(
                r"\b(?:sex|gender)\b\s*[:\-]?\s*([a-z0-9/|,\s]{1,24})",
                context,
                flags=re.IGNORECASE,
            )

            segment = m.group(1) if m else context
            candidates = []
            for token in re.split(r"[/|,\s]+", segment):
                normalized = _normalize_gender_token(token)
                if normalized and normalized not in candidates:
                    candidates.append(normalized)

            if len(candidates) == 1:
                result["gender"] = candidates[0]
                break

        if result["gender"] is not None:
            break

    # Secondary fallback: labeled match in full text.
    if result["gender"] is None:
        m = re.search(
            r"\b(?:sex|gender)\b\s*[:\-]?\s*([a-z0-9/|,\s]{1,20})",
            lower,
            flags=re.IGNORECASE,
        )
        if m:
            candidates = []
            for token in re.split(r"[/|,\s]+", m.group(1)):
                normalized = _normalize_gender_token(token)
                if normalized and normalized not in candidates:
                    candidates.append(normalized)
            if len(candidates) == 1:
                result["gender"] = candidates[0]

    # Final conservative fallback: only use global word if it is unambiguous.
    if result["gender"] is None:
        has_male = bool(re.search(r"\bmale\b", lower))
        has_female = bool(re.search(r"\bfemale\b", lower))
        if has_male ^ has_female:
            result["gender"] = "male" if has_male else "female"

    # --- Weight ---
    for pattern in [
        r"(?:weight|body\s*weight|bw)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:kg|kgs|kilogram)",
        r"(\d+\.?\d*)\s*(?:kg|kgs)\b",
    ]:
        m = re.search(pattern, lower)
        if m:
            val = float(m.group(1))
            if 20 <= val <= 400:
                result["weight"] = val
                break

    # --- Height ---
    for pattern in [
        r"(?:height|stature)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:cm|centimeter)",
        r"(\d+\.?\d*)\s*cm\b",
    ]:
        m = re.search(pattern, lower)
        if m:
            val = float(m.group(1))
            if 50 <= val <= 300:
                result["height"] = val
                break

    # --- Blood sugar (mg/dL) ---
    blood_sugar_patterns = [
        # Handles: "Blood Sugar: 210", "FBS 95", "Blood glucose (fasting): 102 mg/dL"
        r"(?:fasting|random|postprandial|pp|ppbs|fbs|rbs)?\s*(?:blood\s*)?(?:sugar|glucose)\b[^\d]{0,28}?([0-9oOIl|]{2,4}(?:[.,][0-9oOIl|]{1,2})?)",
        # Handles: "FBS: 92", "RBS - 180"
        r"\b(?:fbs|rbs|fpg|ppbs|ppg)\b[^\d]{0,20}?([0-9oOIl|]{2,4}(?:[.,][0-9oOIl|]{1,2})?)",
        # Handles: "Glucose level 145 mg/dL"
        r"(?:glucose|blood\s*glucose)\s*(?:level|reading|value)?\b[^\d]{0,20}?([0-9oOIl|]{2,4}(?:[.,][0-9oOIl|]{1,2})?)",
    ]

    for pattern in blood_sugar_patterns:
        m = re.search(pattern, lower, flags=re.IGNORECASE)
        if not m:
            continue
        val = _parse_ocr_number(m.group(1))
        if val is not None and 20 <= val <= 600:
            result["blood_sugar"] = val
            break

    # Fallback: OCR often splits label/value across lines.
    if result["blood_sugar"] is None:
        lines = [line.strip() for line in re.split(r"[\r\n]+", lower) if line.strip()]
        sugar_keywords = (
            "blood sugar",
            "blood glucose",
            "glucose",
            "fbs",
            "rbs",
            "fpg",
            "ppbs",
            "ppg",
        )
        number_pattern = r"(?<!\d)([0-9oOIl|]{2,4}(?:[.,][0-9oOIl|]{1,2})?)(?!\d)"

        for idx, line in enumerate(lines):
            if not any(keyword in line for keyword in sugar_keywords):
                continue

            context = line
            if idx + 1 < len(lines):
                context = f"{context} {lines[idx + 1]}"

            for match in re.finditer(number_pattern, context, flags=re.IGNORECASE):
                val = _parse_ocr_number(match.group(1))
                if val is not None and 20 <= val <= 600:
                    result["blood_sugar"] = val
                    break

            if result["blood_sugar"] is not None:
                break

    # --- Allergies ---
    allergy_map = {
        "seafood": [
            "seafood",
            "shellfish",
            "shrimp",
            "crab",
            "lobster",
            "fish allergy",
        ],
        "eggs": ["egg", "eggs"],
        "soy": ["soy", "soybean", "soya"],
    }
    for key, keywords in allergy_map.items():
        for kw in keywords:
            if kw in lower:
                if key not in result["allergies"]:
                    result["allergies"].append(key)
                break

    # --- Diet type ---
    if "vegan" in lower:
        result["diet_type"] = "vegan"
    elif "vegetarian" in lower:
        result["diet_type"] = "vegan"

    return result


@dashboard_bp.route("/language-mode", methods=["POST"])
@login_required
@csrf.exempt
def set_language_mode():
    payload = request.get_json(silent=True) or {}
    language = str(payload.get("language", "")).strip().lower()

    if language not in {"km", "en"}:
        return jsonify({"success": False, "message": "មុខងារភាសានេះមិនត្រូវបានគាំទ្រទេ។"}), 400

    session["ui_lang"] = language
    session.modified = True

    return jsonify({"success": True, "language": language})


@dashboard_bp.route("/user/data")
@login_required
@user_required
@permission_required(
    "user.dashboard.read",
    "អ្នកមិនមានសិទ្ធិចូលប្រើទិន្នន័យផ្ទាំងគ្រប់គ្រងទេ។",
    json_response=True,
)
def user_dashboard_data():
    """User dashboard data API endpoint"""
    if session.get("user_guest_mode"):
        return jsonify(
            {
                "user_bmi": None,
                "active_goals": 0,
                "total_diagnoses": 0,
                "upcoming_appointments": 0,
                "diagnoses": [],
            }
        )

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
        condition = primary.get("name", "ការវិនិច្ឆ័យ")
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


@dashboard_bp.route("/user/guest-mode", methods=["POST"])
@login_required
@user_required
@csrf.exempt
@permission_required(
    "user.dashboard.read",
    "អ្នកមិនមានសិទ្ធិប្តូររបៀបភ្ញៀវទេ។",
    json_response=True,
)
def user_guest_mode():
    payload = request.get_json(silent=True) or {}
    enabled = bool(payload.get("enabled", True))

    if enabled:
        session["user_guest_mode"] = True
        if not isinstance(session.get("guest_plan_history"), list):
            session["guest_plan_history"] = []
        session.modified = True
        message = "បានបើករបៀបភ្ញៀវ។"
    else:
        session.pop("user_guest_mode", None)
        session.pop("guest_plan_history", None)
        session.modified = True
        message = "បានបិទរបៀបភ្ញៀវ។ ការរក្សាទុកទៅមូលដ្ឋានទិន្នន័យត្រូវបានស្ដារឡើងវិញ។"

    return jsonify(
        {
            "success": True,
            "guest_mode": bool(session.get("user_guest_mode")),
            "message": message,
        }
    )


@dashboard_bp.route("/user/submit", methods=["POST"])
@login_required
@user_required
@csrf.exempt
@permission_required(
    "user.dashboard.create",
    "អ្នកមិនមានសិទ្ធិបញ្ជូនទិន្នន័យផ្ទាំងគ្រប់គ្រងទេ។",
    json_response=True,
)
def user_dashboard_submit():
    payload = request.get_json(silent=True) or {}
    guest_mode_enabled = bool(session.get("user_guest_mode"))

    try:
        result = DashboardService.save_user_dashboard_submission(
            current_user.id, payload, persist=not guest_mode_enabled
        )

        if guest_mode_enabled:
            profile = result.get("profile", {}) or {}
            metrics = result.get("metrics", {}) or {}
            health = payload.get("health", {}) or {}
            preferences = payload.get("preferences", {}) or {}
            allergies = profile.get("allergies") or health.get("allergies") or []
            guest_entry = {
                "id": f"guest-{uuid.uuid4().hex[:8]}",
                "generated_at": datetime.utcnow().isoformat(),
                "bmi": metrics.get("bmi"),
                "calories": metrics.get("calories"),
                "protein": metrics.get("protein"),
                "sugar": metrics.get("sugar"),
                "fat": metrics.get("fat"),
                "blood_sugar": profile.get("blood_sugar")
                if profile.get("blood_sugar") is not None
                else health.get("blood_sugar"),
                "diet_type": profile.get("diet_type") or health.get("dietType"),
                "meals_per_day": profile.get("meals_per_day")
                or preferences.get("mealsPerDay"),
                "allergies": _localize_allergies(allergies),
            }

            guest_plan_history = session.get("guest_plan_history", [])
            if not isinstance(guest_plan_history, list):
                guest_plan_history = []
            guest_plan_history.insert(0, guest_entry)
            session["guest_plan_history"] = guest_plan_history[:8]
            session.modified = True

        return jsonify(
            {
                "success": True,
                "guest_mode": guest_mode_enabled,
                **result,
            }
        )
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        current_app.logger.exception("Failed to save dashboard submission")
        return jsonify({"success": False, "message": "មិនអាចរក្សាទុកការបញ្ជូនទិន្នន័យបានទេ។"}), 500


@dashboard_bp.route("/user/symptoms")
@login_required
@user_required
@permission_required("user.dashboard.read", "អ្នកមិនមានសិទ្ធិមើលរោគសញ្ញាទេ។")
def get_symptoms():
    """Get available symptoms for user selection"""
    symptoms = [
        {
            "id": 1,
            "name": "ស្រេកទឹកខ្លាំង",
            "description": "មានអារម្មណ៍ស្រេកទឹកញឹកញាប់ជាងធម្មតា",
        },
        {
            "id": 2,
            "name": "នោមញឹកញាប់",
            "description": "ត្រូវការនោមញឹកញាប់ជាងធម្មតា",
        },
        {"id": 3, "name": "អស់កម្លាំង", "description": "មានអារម្មណ៍នឿយហត់ និងខ្វះថាមពល"},
        {
            "id": 4,
            "name": "មើលមិនច្បាស់",
            "description": "ចក្ខុវិស័យព្រិល ឬមិនសូវច្បាស់",
        },
        {
            "id": 5,
            "name": "ស្រកទម្ងន់មិនដឹងមូលហេតុ",
            "description": "ស្រកទម្ងន់ដោយមិនបានព្យាយាម",
        },
        {
            "id": 6,
            "name": "ឃ្លានញឹកញាប់",
            "description": "មានអារម្មណ៍ឃ្លានញឹកញាប់ជាងធម្មតា",
        },
        {
            "id": 7,
            "name": "របួសជាសះយឺត",
            "description": "ស្នាមកាត់ ឬដំបៅដែលជាសះយឺត",
        },
        {
            "id": 8,
            "name": "ឆ្លងជំងឺញឹកញាប់",
            "description": "ឈឺញឹកញាប់ជាងធម្មតា",
        },
    ]

    return jsonify({"symptoms": symptoms})


@dashboard_bp.route("/user/diagnosis", methods=["POST"])
@login_required
@user_required
@permission_required(
    "user.dashboard.create",
    "អ្នកមិនមានសិទ្ធិដំណើរការវិនិច្ឆ័យទេ។",
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
        "name": "ហានិភ័យជំងឺទឹកនោមផ្អែមប្រភេទទី 2",
        "description": "ផ្អែកលើរោគសញ្ញារបស់អ្នក អ្នកអាចមានហានិភ័យជំងឺទឹកនោមផ្អែមប្រភេទទី 2",
        "confidence": 75,
    }

    recommendations = [
        "សូមពិគ្រោះជាមួយអ្នកជំនាញសុខាភិបាល ដើម្បីវិនិច្ឆ័យឱ្យបានត្រឹមត្រូវ",
        "សូមតាមដានកម្រិតជាតិស្ករក្នុងឈាមជាប្រចាំ",
        "រក្សារបបអាហារដែលមានសុខភាពល្អ និងជាតិស្ករចម្រាញ់ទាប",
        "ធ្វើសកម្មភាពរាងកាយឱ្យបានទៀងទាត់",
        "ផឹកទឹកឱ្យគ្រប់គ្រាន់ និងគេងឱ្យបានគ្រប់",
    ]

    next_steps = [
        "កំណត់ពេលជួបវេជ្ជបណ្ឌិតរបស់អ្នក",
        "កត់ត្រារោគសញ្ញាប្រចាំថ្ងៃ",
        "សិក្សាពីវិធីគ្រប់គ្រងជំងឺទឹកនោមផ្អែម",
        "ពិចារណាកែប្រែរបបអាហារ",
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
    flash(
        "អ្នកមិនមានសិទ្ធិចូលប្រើទំព័រនេះទេ។"
        if _is_khmer_ui()
        else "You do not have permission to access this page.",
        "danger",
    )
    return redirect(url_for("auth.login"))


@dashboard_bp.errorhandler(404)
def not_found(e):
    flash("រកមិនឃើញទំព័រនេះទេ។" if _is_khmer_ui() else "Page not found.", "warning")
    return redirect(url_for("main.home"))
