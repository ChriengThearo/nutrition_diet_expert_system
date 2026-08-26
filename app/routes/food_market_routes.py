from flask import Blueprint, current_app, jsonify, request, redirect, url_for
from flask_login import current_user, login_required

from app.models.doctor_food_favorite import DoctorFoodFavorite
from app.routes.dashboard_routes import doctor_required
from app.services.usda_service import USDAService
from extensions import csrf, db

food_market_bp = Blueprint("food_market", __name__, url_prefix="/dashboard/doctor/food-market")


def _error(message, status=400):
    return jsonify({"success": False, "message": message}), status


@food_market_bp.route("")
@login_required
@doctor_required
def page():
    return redirect(url_for("dashboard.doctor_dashboard", section="food-market"))


@food_market_bp.route("/categories", methods=["GET"])
@login_required
@doctor_required
def categories():
    return jsonify({"success": True, "categories": list(USDAService.CATEGORIES)})


@food_market_bp.route("/search", methods=["GET", "POST"])
@csrf.exempt
@login_required
@doctor_required
def search():
    payload = request.get_json(silent=True) or {}
    query = request.args.get("q", "") if request.method == "GET" else payload.get("query", "")
    category = request.args.get("category", "all") if request.method == "GET" else payload.get("category", "all")
    page = request.args.get("page", 1, type=int) if request.method == "GET" else payload.get("page", 1)
    page_size = request.args.get("page_size", 12, type=int) if request.method == "GET" else payload.get("page_size", 12)
    try:
        result = USDAService.search(query=query, page=page, page_size=page_size, category=category)
        return jsonify({"success": True, **result})
    except ValueError as exc:
        return _error(str(exc))
    except RuntimeError as exc:
        return _error(str(exc), 503)


@food_market_bp.route("/<int:fdc_id>")
@login_required
@doctor_required
def detail(fdc_id):
    try:
        return jsonify({"success": True, "food": USDAService.get(fdc_id)})
    except ValueError as exc:
        return _error(str(exc))
    except RuntimeError as exc:
        return _error(str(exc), 503)


@food_market_bp.route("/compare", methods=["POST"])
@csrf.exempt
@login_required
@doctor_required
def compare():
    foods = (request.get_json(silent=True) or {}).get("foods")
    if not isinstance(foods, list) or len(foods) < 2 or len(foods) > 5:
        return _error("Select two to five USDA foods to compare.")
    return jsonify({"success": True, "foods": foods, "interpretation": "Comparison uses only the USDA values displayed in this table."})


@food_market_bp.route("/ai-search", methods=["POST"])
@csrf.exempt
@login_required
@doctor_required
def ai_search():
    request_text = str((request.get_json(silent=True) or {}).get("query") or "").strip()
    if len(request_text) < 2:
        return _error("Describe the food search you need.")
    terms = {"protein": "protein", "sodium": "sodium", "fiber": "fiber", "calorie": "calorie", "calories": "calorie", "calcium": "calcium", "iron": "iron"}
    query = next((value for key, value in terms.items() if key in request_text.lower()), request_text)
    return jsonify({"success": True, "query": query, "message": "Search intent prepared. Nutrition values will come from USDA results.", "ai_provider": "not configured"})


@food_market_bp.route("/favorites", methods=["GET", "POST"])
@csrf.exempt
@login_required
@doctor_required
def favorites():
    if request.method == "GET":
        rows = DoctorFoodFavorite.query.filter_by(doctor_id=current_user.id).order_by(DoctorFoodFavorite.created_at.desc()).all()
        return jsonify({"success": True, "foods": [row.food_snapshot for row in rows]})
    food = (request.get_json(silent=True) or {}).get("food")
    if not isinstance(food, dict) or not food.get("fdc_id"):
        return _error("A USDA food record is required.")
    existing = DoctorFoodFavorite.query.filter_by(doctor_id=current_user.id, fdc_id=int(food["fdc_id"])).first()
    if not existing:
        db.session.add(DoctorFoodFavorite(doctor_id=current_user.id, fdc_id=int(food["fdc_id"]), food_name=str(food.get("name") or "Unnamed food"), food_snapshot=food))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to save food favorite")
            return _error("Could not save this food right now.", 500)
    return jsonify({"success": True})


@food_market_bp.route("/favorites/<int:fdc_id>", methods=["DELETE"])
@csrf.exempt
@login_required
@doctor_required
def delete_favorite(fdc_id):
    row = DoctorFoodFavorite.query.filter_by(doctor_id=current_user.id, fdc_id=fdc_id).first()
    if not row:
        return _error("Saved food not found.", 404)
    db.session.delete(row)
    db.session.commit()
    return jsonify({"success": True})
