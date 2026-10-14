from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    send_from_directory,
    current_app,
    Response,
)
from flask_login import login_required, current_user
import os
import math
from app.public_copy import ADULT, CHILD
from app.seo import production_url, is_production_request
from app.services.bmi_reference import child_bmi_result
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
    return render_template("main/home.html", ui_lang="en")


@main_bp.route("/km/")
def home_km():
    return render_template("main/home.html", ui_lang="km")


@main_bp.route("/robots.txt")
def robots_txt():
    if is_production_request():
        body = "User-agent: *\nAllow: /\nSitemap: " + production_url("/sitemap.xml") + "\n"
    else:
        body = "User-agent: *\nAllow: /\n"
    return Response(body, mimetype="text/plain")


@main_bp.route("/sitemap.xml")
def sitemap_xml():
    if not is_production_request():
        return Response("", status=404, mimetype="application/xml")
    paths = ("/", "/km/", "/bmi", "/km/bmi")
    urls = "".join(f"<url><loc>{production_url(path)}</loc></url>" for path in paths)
    return Response('<?xml version="1.0" encoding="UTF-8"?>'
                    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                    mimetype="application/xml")


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
    return _adult_bmi("en")


@main_bp.route("/bmi/")
def bmi_trailing_slash():
    return redirect(url_for("main.bmi"), code=308)


@main_bp.route("/km/bmi", methods=["GET", "POST"])
def bmi_km():
    return _adult_bmi("km")


@main_bp.route("/km/bmi/")
def bmi_km_trailing_slash():
    return redirect(url_for("main.bmi_km"), code=308)


def _adult_bmi(lang):
    copy = ADULT[lang].copy()
    if not current_app.config.get("CHILD_BMI_ENABLED", False):
        copy["age_error"] = copy["age_disabled"]
    values = {}
    if request.method == "POST":
        try:
            age = int(request.form["age"])
            height_cm = float(request.form["height"])
            weight = float(request.form["weight"])
            if age < 20 or not (math.isfinite(height_cm) and 50 <= height_cm <= 300
                                              and math.isfinite(weight) and 10 <= weight <= 500):
                raise ValueError
            raw_bmi = weight / (height_cm / 100) ** 2
            values = {"bmi": round(raw_bmi, 2),
                      "category_key": get_bmi_category(raw_bmi).lower().replace(" ", "_"),
                      "age": age, "height_val": height_cm, "weight_val": weight}
        except (KeyError, ValueError, ZeroDivisionError):
            flash(copy["age_error"], "error")
    return render_template("main/bmi.html", page_lang=lang, t=copy,
                           server_result=values or None)


@main_bp.route("/bmi/child-teen", methods=["GET", "POST"])
def child_bmi():
    return _child_bmi("en")


@main_bp.route("/km/bmi/child-teen", methods=["GET", "POST"])
def child_bmi_km():
    return _child_bmi("km")


def _child_bmi(lang):
    result = None
    error = None
    values = {key: request.form.get(key, "") for key in
              ("age_years", "age_months", "sex", "height_cm", "weight_kg")}
    if request.method == "POST":
        try:
            age_years = int(values["age_years"])
            if age_years >= 20:
                return redirect(url_for("main.bmi_km" if lang == "km" else "main.bmi"), code=303)
            age_months = int(values["age_months"])
            result = child_bmi_result(age_years, age_months, values["sex"],
                                      values["height_cm"], values["weight_kg"])
        except (ValueError, TypeError):
            error = CHILD[lang]["input_error"]
    rendered = render_template("main/child_bmi.html", page_lang=lang, t=CHILD[lang],
                               result=result, error=error, values=values)
    return Response(rendered, status=400 if error else 200,
                    headers={"Cache-Control": "no-store"})


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
        return "Healthy weight"
    elif 25 <= bmi < 30:
        return "Overweight"
    else:
        return "Obesity"
