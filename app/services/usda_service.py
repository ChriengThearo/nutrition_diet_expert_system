import os
import re
from typing import Any

import requests
from flask import current_app


class USDAService:
    BASE_URL = "https://api.nal.usda.gov/fdc/v1"
    TIMEOUT = (3.05, 12)
    LIMIT = 25
    CATEGORY_QUERIES = {
        "all": "food",
        "fruits": "fruit",
        "vegetables": "vegetable",
        "grains": "grain",
        "meat": "meat",
        "poultry": "poultry",
        "fish": "fish",
        "eggs": "egg",
        "dairy": "dairy",
        "legumes": "legume",
        "nuts": "nuts seeds",
        "beverages": "beverage",
        "snacks": "snack",
        "other": "food",
    }
    CATEGORIES = tuple(CATEGORY_QUERIES)

    @staticmethod
    def _api_key():
        return os.getenv("USDA_API_KEY") or current_app.config.get("USDA_API_KEY")

    @classmethod
    def _request(cls, method: str, path: str, **kwargs):
        api_key = cls._api_key()
        if not api_key:
            raise RuntimeError("USDA API is not configured.")
        params = kwargs.pop("params", {})
        params["api_key"] = api_key
        try:
            response = requests.request(
                method, f"{cls.BASE_URL}{path}", params=params, timeout=cls.TIMEOUT, **kwargs
            )
            if response.status_code == 429:
                raise RuntimeError("USDA rate limit reached. Please try again shortly.")
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise RuntimeError("USDA request timed out. Please try again.") from exc
        except requests.RequestException as exc:
            current_app.logger.warning("USDA request failed: %s", exc)
            raise RuntimeError("USDA is temporarily unavailable.") from exc

    @staticmethod
    def _nutrient(food: dict[str, Any], names: set[str]):
        for item in food.get("foodNutrients", []) or []:
            nutrient = item.get("nutrient") if isinstance(item.get("nutrient"), dict) else {}
            name = str(item.get("nutrientName") or nutrient.get("name") or "").lower()
            number = str(item.get("nutrientNumber") or nutrient.get("number") or "")
            if name in names or number in names:
                value = item.get("value")
                if value in (None, ""):
                    value = item.get("amount")
                return value if value not in (None, "") else None
        return None

    @classmethod
    def classify(cls, food: dict[str, Any]) -> str:
        """Classify from USDA foodCategory first, then explicit description terms."""
        raw = " ".join(
            str(food.get(key) or "")
            for key in ("foodCategory", "category", "description", "foodDescription")
        ).lower()
        raw = re.sub(r"[^a-z0-9& ]+", " ", raw)
        rules = (
            ("fruits", r"fruit|apple|banana|berry|citrus|melon|grape|mango|pear|peach"),
            ("vegetables", r"vegetable|lettuce|spinach|broccoli|carrot|tomato|pepper|cucumber|cabbage|potato"),
            ("poultry", r"poultry|chicken|turkey|duck"),
            ("fish", r"fish|seafood|salmon|tuna|cod|shrimp|shellfish"),
            ("meat", r"meat|beef|pork|lamb|veal|goat"),
            ("eggs", r"egg"),
            ("dairy", r"dairy|milk|cheese|yogurt|butter|cream"),
            ("legumes", r"legume|bean|lentil|pea|chickpea|soy|tofu"),
            ("nuts", r"nut|seed|almond|walnut|peanut|cashew|pistachio"),
            ("grains", r"grain|rice|wheat|oat|barley|rye|corn|pasta|bread|cereal|quinoa"),
            ("beverages", r"beverage|drink|juice|tea|coffee|water|soda"),
            ("snacks", r"snack|chip|cracker|popcorn|bar"),
        )
        for category, pattern in rules:
            if re.search(pattern, raw):
                return category
        return "other"

    @classmethod
    def normalize(cls, food: dict[str, Any]) -> dict[str, Any]:
        return {
            "fdc_id": food.get("fdcId"),
            "name": food.get("description") or food.get("foodDescription") or "Unnamed food",
            "data_type": food.get("dataType"),
            "brand_owner": food.get("brandOwner"),
            "brand_name": food.get("brandName"),
            "food_category": food.get("foodCategory") or food.get("category"),
            "category": cls.classify(food),
            "serving_size": food.get("servingSize"),
            "serving_size_unit": food.get("servingSizeUnit"),
            "nutrients": {
                "calories": cls._nutrient(food, {"208", "1008"}),
                "protein_g": cls._nutrient(food, {"protein", "203"}),
                "fat_g": cls._nutrient(food, {"total lipid (fat)", "204"}),
                "carbohydrates_g": cls._nutrient(food, {"carbohydrate, by difference", "205"}),
                "fiber_g": cls._nutrient(food, {"fiber, total dietary", "291"}),
                "sugars_g": cls._nutrient(food, {"sugars, total including nleas", "269"}),
                "sodium_mg": cls._nutrient(food, {"sodium, na", "307"}),
            },
            "ingredients": food.get("ingredients"),
            "data_source": "USDA FoodData Central",
        }

    @classmethod
    def search(cls, query: str = "", page: int = 1, page_size: int = 12, category: str = "all", filters=None):
        category = str(category or "all").strip().lower()
        if category not in cls.CATEGORY_QUERIES:
            category = "all"
        query = str(query or "").strip()
        if len(query) == 1:
            raise ValueError("Enter at least two characters to search foods.")
        page = max(1, min(int(page or 1), 1000))
        page_size = max(1, min(int(page_size or 12), cls.LIMIT))
        search_query = query or cls.CATEGORY_QUERIES[category]
        data = cls._request(
            "POST", "/foods/search", json={
                "query": search_query,
                "pageNumber": page,
                "pageSize": page_size,
                "dataType": filters or ["Foundation", "SR Legacy", "Survey (FNDDS)", "Branded"],
            }
        )
        foods = [cls.normalize(item) for item in data.get("foods", [])]
        if category != "all":
            # USDA commonly classifies chicken/turkey under poultry; include
            # those records in the broader Meat view as well.
            allowed = {category}
            if category == "meat":
                allowed.add("poultry")
            foods = [food for food in foods if food["category"] in allowed]
        return {
            "foods": foods,
            "total": data.get("totalHits", len(foods)),
            "page": page,
            "page_size": page_size,
            "category": category,
        }

    @classmethod
    def get(cls, fdc_id: int):
        try:
            fdc_id = int(fdc_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid food identifier.") from exc
        if fdc_id <= 0:
            raise ValueError("Invalid food identifier.")
        return cls.normalize(cls._request("GET", f"/food/{fdc_id}"))
