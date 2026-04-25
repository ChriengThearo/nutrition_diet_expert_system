import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from extensions import db


SEED_PATH = Path(__file__).resolve().parent / "tbl_foods.json"
ALLOWED_TYPES = {"general", "seafood", "eggs", "soy"}


def _normalize_food_type(value):
    token = str(value or "general").strip().lower() or "general"
    return token if token in ALLOWED_TYPES else "general"


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def main():
    app = create_app()

    with app.app_context():
        rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        now_iso = datetime.now(timezone.utc).isoformat()

        db.session.execute(
            text(
                "ALTER TABLE public.tbl_foods "
                "ADD COLUMN IF NOT EXISTS food_type VARCHAR(20) NOT NULL DEFAULT 'general'"
            )
        )

        id_to_food_type = {}
        for row in rows:
            try:
                food_id = int(row.get("id"))
            except Exception:
                continue
            id_to_food_type[food_id] = _normalize_food_type(row.get("food_type"))

        if id_to_food_type:
            db.session.execute(
                text("UPDATE public.tbl_foods SET food_type = :food_type WHERE id = :id"),
                [
                    {"id": food_id, "food_type": food_type}
                    for food_id, food_type in id_to_food_type.items()
                ],
            )

        before_count = db.session.execute(
            text("SELECT COUNT(*) FROM public.tbl_foods")
        ).scalar() or 0
        seeded = False

        if int(before_count) == 0:
            payload = []
            for row in rows:
                try:
                    food_id = int(row.get("id"))
                except Exception:
                    continue
                payload.append(
                    {
                        "id": food_id,
                        "name": str(row.get("name") or "").strip() or f"Food {food_id}",
                        "photo": str(row.get("photo") or "").strip() or None,
                        "is_gevan": _to_bool(row.get("is_gevan")),
                        "food_type": _normalize_food_type(row.get("food_type")),
                        "description": str(row.get("description") or "").strip() or None,
                        "calories": row.get("calories"),
                        "protein": row.get("protein"),
                        "sugar": row.get("sugar"),
                        "fat": row.get("fat"),
                        "created_at": row.get("created_at") or now_iso,
                        "updated_at": row.get("updated_at") or now_iso,
                    }
                )

            if payload:
                db.session.execute(
                    text(
                        """
                        INSERT INTO public.tbl_foods
                            (id, name, photo, is_gevan, food_type, description, calories, protein, sugar, fat, created_at, updated_at)
                        VALUES
                            (:id, :name, :photo, :is_gevan, :food_type, :description, :calories, :protein, :sugar, :fat, :created_at, :updated_at)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            photo = EXCLUDED.photo,
                            is_gevan = EXCLUDED.is_gevan,
                            food_type = EXCLUDED.food_type,
                            description = EXCLUDED.description,
                            calories = EXCLUDED.calories,
                            protein = EXCLUDED.protein,
                            sugar = EXCLUDED.sugar,
                            fat = EXCLUDED.fat,
                            updated_at = EXCLUDED.updated_at
                        """
                    ),
                    payload,
                )
                seeded = True

        db.session.commit()

        after_count = db.session.execute(
            text("SELECT COUNT(*) FROM public.tbl_foods")
        ).scalar() or 0

        print(f"tbl_foods_before={int(before_count)}")
        print(f"seed_applied={seeded}")
        print(f"tbl_foods_after={int(after_count)}")


if __name__ == "__main__":
    main()
