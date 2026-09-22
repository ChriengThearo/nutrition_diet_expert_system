"""Seed only the seven isolated usda_market_* tables from local usda_all_v2."""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db

TABLES = (
    ("usda_market_categories", "usda_all_v2.categories", ("code", "name"), ("code",)),
    ("usda_market_foods", "usda_all_v2.foods", ("fdc_id", "normalized_name", "name", "category_group", "data_type", "source_category", "source_food_category_id", "publication_date", "energy_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"), ("fdc_id",)),
    ("usda_market_nutrients", "usda_all_v2.nutrients", ("nutrient_id", "name", "unit_name", "rank"), ("nutrient_id",)),
    ("usda_market_food_nutrients", "usda_all_v2.food_nutrients", ("fdc_id", "nutrient_id", "amount"), ("fdc_id", "nutrient_id")),
    ("usda_market_nutrition_summary", "usda_all_v2.nutrition_summary", ("fdc_id", "calories_kcal", "protein_g", "carbohydrates_g", "fat_g", "fiber_g", "sugars_g", "sodium_mg"), ("fdc_id",)),
    ("usda_market_catalog", "food_market.catalog", ("fdc_id", "description", "data_type", "food_category_id", "publication_date", "category_name", "brand", "brand_name", "ingredients", "serving_size", "serving_size_unit", "household_serving_fulltext", "energy_kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "category_group", "is_category_relevant"), ("fdc_id",)),
    ("usda_market_catalog_stats", "food_market.catalog_stats", ("category_group", "all_food_count", "food_count"), ("category_group",)),
)


def source_connection(args):
    if args.source_url:
        return psycopg.connect(args.source_url)
    required = ("DB_HOST", "DB_PORT", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD")
    values = {}
    for line in Path(args.source_env).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError(f"Source settings missing: {', '.join(missing)}")
    return psycopg.connect(
        host=values["DB_HOST"], port=values["DB_PORT"], dbname=values["DB_DATABASE"],
        user=values["DB_USERNAME"], password=values["DB_PASSWORD"],
    )


def upsert_sql(target, columns, keys):
    columns_sql = ", ".join(columns)
    values_sql = ", ".join(f":{column}" for column in columns)
    updates = [column for column in columns if column not in keys]
    update_sql = ", ".join(f"{column} = EXCLUDED.{column}" for column in updates)
    return text(f"INSERT INTO {target} ({columns_sql}) VALUES ({values_sql}) ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {update_sql}")


def import_table(source, target_connection, target, source_table, columns, keys, batch_size):
    selected = ", ".join(columns)
    with source.cursor(name=f"source_{target}") as cursor:
        cursor.execute(f"SELECT {selected} FROM {source_table}")
        statement = upsert_sql(target, columns, keys)
        total = 0
        while rows := cursor.fetchmany(batch_size):
            payload = [dict(zip(columns, row)) for row in rows]
            target_connection.execute(statement, payload)
            total += len(payload)
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", default=os.getenv("USDA_SOURCE_DATABASE_URL"))
    parser.add_argument("--source-env", default=r"D:\Other\Temporary_Store\CODE\usda_api\.env")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 5000:
        raise SystemExit("--batch-size must be between 1 and 5000")

    app = create_app()
    with app.app_context(), source_connection(args) as source, db.engine.begin() as target_connection:
        imported = {}
        for target, source_table, columns, keys in TABLES:
            imported[target] = import_table(source, target_connection, target, source_table, columns, keys, args.batch_size)
            print(f"Seeded {imported[target]:,} rows into {target}.")
        for target, _, _, _ in TABLES:
            expected = imported[target]
            actual = target_connection.execute(text(f"SELECT count(*) FROM {target}")).scalar_one()
            if actual != expected:
                raise RuntimeError(f"{target} validation failed: expected {expected}, found {actual}")
    print("USDA market import completed and validated.")


if __name__ == "__main__":
    main()
