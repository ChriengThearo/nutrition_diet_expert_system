from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    send_from_directory,
    current_app,
)
from flask_login import login_required, current_user
import os
from app.models.goal import GoalsTable
from app.models.diet_rule import DietRulesTable
from app.models.food import FoodsTable
from app.models.food_group import FoodGroupTable
from app.forms.diet_rule_forms import DietRuleForm
from app.services.diet_rule_service import DietRuleService
from extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("main/home.html")


@main_bp.route("/project-poster")
def project_poster():
    return render_template("main/diet_poster.html")


@main_bp.route("/admin")
@login_required
def admin_shortcut():
    if not current_user.has_role("admin"):
        flash("Admin access required", "danger")
        return redirect(url_for("auth.login"))
    return redirect(url_for("dashboard.admin_dashboard"))


@main_bp.route("/admin/<path:subpath>")
@login_required
def admin_shortcut_subpath(subpath: str):
    if not current_user.has_role("admin"):
        flash("Admin access required", "danger")
        return redirect(url_for("auth.login"))
    target = subpath.strip("/")
    return redirect(f"{url_for('dashboard.admin_dashboard')}/{target}")


@main_bp.route("/bmi", methods=["GET", "POST"])
def bmi():
    if request.method == "POST":
        try:
            height = float(request.form["height"]) / 100  # Convert cm to m
            weight = float(request.form["weight"])
            bmi_value = round(weight / (height**2), 2)
            category = get_bmi_category(bmi_value)
            return render_template(
                "main/bmi.html",
                bmi=bmi_value,
                category=category,
                age=request.form.get("age", ""),
                gender=request.form.get("gender", "male"),
                height_val=request.form.get("height", ""),
                weight_val=request.form.get("weight", ""),
            )
        except ValueError:
            flash("Please enter valid numbers for height and weight.", "error")
    return render_template("main/bmi.html")


@main_bp.route("/match", methods=["GET", "POST"])
def match():
    goals = GoalsTable.query.all()
    if request.method == "POST":
        goal_id = request.form.get("goal")
        bmi_raw = (request.form.get("bmi") or "").strip()
        bmi = float(bmi_raw) if bmi_raw else None

        # Find matching diet rules based on goal
        goal = GoalsTable.query.get(goal_id)

        if goal:
            # Get diet rules that match the selected goal
            matching_rules = DietRulesTable.query.filter(
                DietRulesTable.goals.contains(goal)
            ).all()
            return render_template(
                "main/match.html",
                goals=goals,
                matching_rules=matching_rules,
                selected_goal=goal,
                bmi=bmi,
            )
        flash("Please select a goal.", "error")
    return render_template("main/match.html", goals=goals)


@main_bp.route("/rules")
def rules():
    rules = DietRulesTable.query.all()
    return render_template("main/rules.html", rules=rules)


@main_bp.route("/rules/create", methods=["GET", "POST"])
def create_rule():
    form = DietRuleForm()

    if form.validate_on_submit():
        try:
            # Prepare data for service
            rule_data = {
                "rule_name": form.rule_name.data,
                "description": form.description.data,
                "conditions": form.conditions.data,
                "goals": form.goals.data,
                "active": form.active.data,
            }

            # Create rule using service
            rule = DietRuleService.create_diet_rule(rule_data)

            flash(f'Diet rule "{rule.rule_name}" created successfully!', "success")
            return redirect(url_for("main.rules"))

        except Exception as e:
            flash(f"Error creating diet rule: {str(e)}", "error")

    return render_template("main/create_rule.html", form=form)


@main_bp.route("/images/<path:filename>")
def images(filename):
    images_dir = os.path.join(current_app.static_folder, "images")
    return send_from_directory(images_dir, filename)


@main_bp.route("/foods/<int:rule_id>")
def foods(rule_id):
    rule = DietRulesTable.query.get_or_404(rule_id)
    # Get foods associated with this rule via food groups -> rule_food_map
    try:
        rule_food_maps = [
            group.rule_food_map
            for group in FoodGroupTable.query.filter_by(diet_rule_id=rule_id).all()
            if group.rule_food_map is not None
        ]
    except Exception:
        rule_food_maps = []
    foods = [
        (rfm.food or rfm.cooked_food, rfm.notes)
        for rfm in rule_food_maps
        if (rfm.food or rfm.cooked_food) is not None
    ]
    return render_template("main/foods.html", rule=rule, foods=foods)


@main_bp.route("/qa", methods=["GET", "POST"])
def qa():
    question = None
    answer = None

    if request.method == "POST":
        question = request.form.get("question")
        # For simplicity, provide a basic answer. In a real app, this could integrate with an AI service.
        answer = f"Thank you for your question: '{question}'. This is a placeholder answer. Please consult a healthcare professional for personalized advice."

    return render_template("main/qa.html", question=question, answer=answer)


def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight"
    elif 18.5 <= bmi < 25:
        return "Normal weight"
    elif 25 <= bmi < 30:
        return "Overweight"
    else:
        return "Obese"
