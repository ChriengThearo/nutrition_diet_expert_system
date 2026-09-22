"""Local USDA Food Market queries backed by seeded usda_market_* tables."""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db


class USDAService:
    CATEGORY_GROUPS = {
        "all": None, "fruits": "Fruits", "vegetables": "Vegetables", "grains": "Grains",
        "meat": "Meat", "poultry": "Poultry", "fish": "Fish & Seafood", "eggs": "Eggs",
        "dairy": "Dairy", "legumes": "Legumes", "nuts": "Nuts & Seeds", "beverages": "Beverages",
        "snacks": "Snacks",
    }
    CATEGORIES = tuple(CATEGORY_GROUPS)
    GROUP_TO_CATEGORY = {group: key for key, group in CATEGORY_GROUPS.items() if group}
    LIMIT = 48

    @staticmethod
    def _number(value):
        return float(value) if isinstance(value, Decimal) else value

    @classmethod
    def _payload(cls, row):
        data = dict(row)
        return {
            "fdc_id": int(data["fdc_id"]), "name": data["description"], "data_type": data["data_type"],
            "brand_owner": data["brand"] or None, "brand_name": data["brand_name"] or None,
            "food_category": data["category_name"],
            "category": cls.GROUP_TO_CATEGORY.get(data["category_group"], "all"),
            "serving_size": cls._number(data.get("serving_size")),
            "serving_size_unit": data["serving_size_unit"] or None,
            "ingredients": data["ingredients"] or None,
            "data_source": "Local USDA FoodData Central snapshot",
            "nutrients": {
                "calories": cls._number(data.get("calories_kcal")),
                "protein_g": cls._number(data.get("protein_g")),
                "fat_g": cls._number(data.get("fat_g")),
                "carbohydrates_g": cls._number(data.get("carbohydrates_g")),
                "fiber_g": cls._number(data.get("fiber_g")),
                "sugars_g": cls._number(data.get("sugars_g")),
                "sodium_mg": cls._number(data.get("sodium_mg")),
            },
        }

    @classmethod
    def search(cls, query="", page=1, page_size=12, category="all", filters=None):
        category = str(category or "all").strip().lower()
        if category not in cls.CATEGORY_GROUPS:
            category = "all"
        query = str(query or "").strip()
        if len(query) == 1:
            raise ValueError("Enter at least two characters to search foods.")
        page, page_size = max(1, min(int(page or 1), 1000)), max(1, min(int(page_size or 12), cls.LIMIT))
        clauses, params = [], {"limit": page_size, "offset": (page - 1) * page_size}
        group = cls.CATEGORY_GROUPS[category]
        if group:
            clauses.append("c.category_group = :category_group")
            params["category_group"] = group
        for index, term in enumerate(query.split()[:8]):
            key = f"term_{index}"
            clauses.append(f"(c.description ILIKE :{key} OR c.brand ILIKE :{key})")
            params[key] = f"%{term}%"
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        select = """
            SELECT c.fdc_id, c.description, c.data_type, c.brand, c.brand_name, c.category_name,
                   c.category_group, c.serving_size, c.serving_size_unit, c.ingredients,
                   n.calories_kcal, n.protein_g, n.carbohydrates_g, n.fat_g, n.fiber_g,
                   n.sugars_g, n.sodium_mg
            FROM usda_market_catalog c
            JOIN usda_market_nutrition_summary n ON n.fdc_id = c.fdc_id
        """
        try:
            with db.engine.connect() as connection:
                rows = connection.execute(text(f"{select} {where} ORDER BY c.description, c.fdc_id LIMIT :limit OFFSET :offset"), params).mappings().all()
                total = connection.execute(text(f"SELECT count(*) FROM usda_market_catalog c {where}"), params).scalar_one()
        except SQLAlchemyError as exc:
            raise RuntimeError("The local USDA food market is unavailable.") from exc
        return {"foods": [cls._payload(row) for row in rows], "total": int(total), "page": page, "page_size": page_size, "category": category}

    @classmethod
    def get(cls, fdc_id):
        try:
            fdc_id = int(fdc_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid food identifier.") from exc
        try:
            with db.engine.connect() as connection:
                row = connection.execute(text("""
                SELECT c.fdc_id, c.description, c.data_type, c.brand, c.brand_name, c.category_name,
                       c.category_group, c.serving_size, c.serving_size_unit, c.ingredients,
                       n.calories_kcal, n.protein_g, n.carbohydrates_g, n.fat_g, n.fiber_g,
                       n.sugars_g, n.sodium_mg
                FROM usda_market_catalog c
                JOIN usda_market_nutrition_summary n ON n.fdc_id = c.fdc_id
                WHERE c.fdc_id = :fdc_id
                """), {"fdc_id": fdc_id}).mappings().first()
        except SQLAlchemyError as exc:
            raise RuntimeError("The local USDA food market is unavailable.") from exc
        if row is None:
            raise ValueError("Food not found.")
        return cls._payload(row)
