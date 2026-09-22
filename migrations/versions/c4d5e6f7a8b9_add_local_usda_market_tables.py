"""add isolated local USDA Food Market tables

Revision ID: c4d5e6f7a8b9
Revises: b3f7a1c8d245
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b3f7a1c8d245"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usda_market_categories",
        sa.Column("code", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
    )
    op.create_table(
        "usda_market_foods",
        sa.Column("fdc_id", sa.BigInteger(), primary_key=True),
        sa.Column("normalized_name", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category_group", sa.String(80), sa.ForeignKey("usda_market_categories.code"), nullable=False),
        sa.Column("data_type", sa.String(80), nullable=False),
        sa.Column("source_category", sa.Text(), nullable=False),
        sa.Column("source_food_category_id", sa.String(80)),
        sa.Column("publication_date", sa.Date()),
        sa.Column("energy_kcal", sa.Numeric(18, 6)),
        sa.Column("protein_g", sa.Numeric(18, 6)),
        sa.Column("carbs_g", sa.Numeric(18, 6)),
        sa.Column("fat_g", sa.Numeric(18, 6)),
        sa.Column("fiber_g", sa.Numeric(18, 6)),
    )
    op.create_index("ix_usda_market_foods_category_name", "usda_market_foods", ["category_group", "name"])
    op.create_table(
        "usda_market_nutrients",
        sa.Column("nutrient_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("unit_name", sa.String(32), nullable=False),
        sa.Column("rank", sa.Numeric(18, 6)),
    )
    op.create_table(
        "usda_market_food_nutrients",
        sa.Column("fdc_id", sa.BigInteger(), sa.ForeignKey("usda_market_foods.fdc_id"), primary_key=True),
        sa.Column("nutrient_id", sa.String(32), sa.ForeignKey("usda_market_nutrients.nutrient_id"), primary_key=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
    )
    op.create_index("ix_usda_market_food_nutrients_nutrient", "usda_market_food_nutrients", ["nutrient_id"])
    op.create_table(
        "usda_market_nutrition_summary",
        sa.Column("fdc_id", sa.BigInteger(), sa.ForeignKey("usda_market_foods.fdc_id"), primary_key=True),
        sa.Column("calories_kcal", sa.Numeric(18, 6)),
        sa.Column("protein_g", sa.Numeric(18, 6)),
        sa.Column("carbohydrates_g", sa.Numeric(18, 6)),
        sa.Column("fat_g", sa.Numeric(18, 6)),
        sa.Column("fiber_g", sa.Numeric(18, 6)),
        sa.Column("sugars_g", sa.Numeric(18, 6)),
        sa.Column("sodium_mg", sa.Numeric(18, 6)),
    )
    op.create_table(
        "usda_market_catalog",
        sa.Column("fdc_id", sa.BigInteger(), sa.ForeignKey("usda_market_foods.fdc_id"), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("data_type", sa.String(80), nullable=False),
        sa.Column("food_category_id", sa.String(80)),
        sa.Column("publication_date", sa.String(32), nullable=False, server_default=""),
        sa.Column("category_name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False, server_default=""),
        sa.Column("brand_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("ingredients", sa.Text(), nullable=False, server_default=""),
        sa.Column("serving_size", sa.Numeric(18, 6)),
        sa.Column("serving_size_unit", sa.String(32), nullable=False, server_default=""),
        sa.Column("household_serving_fulltext", sa.Text(), nullable=False, server_default=""),
        sa.Column("energy_kcal", sa.Numeric(18, 6)),
        sa.Column("protein_g", sa.Numeric(18, 6)),
        sa.Column("carbs_g", sa.Numeric(18, 6)),
        sa.Column("fat_g", sa.Numeric(18, 6)),
        sa.Column("fiber_g", sa.Numeric(18, 6)),
        sa.Column("category_group", sa.String(80), sa.ForeignKey("usda_market_categories.code"), nullable=False),
        sa.Column("is_category_relevant", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_usda_market_catalog_category_name", "usda_market_catalog", ["category_group", "description"])
    op.create_table(
        "usda_market_catalog_stats",
        sa.Column("category_group", sa.String(80), sa.ForeignKey("usda_market_categories.code"), primary_key=True),
        sa.Column("all_food_count", sa.BigInteger(), nullable=False),
        sa.Column("food_count", sa.BigInteger(), nullable=False),
    )


def downgrade():
    op.drop_table("usda_market_catalog_stats")
    op.drop_index("ix_usda_market_catalog_category_name", table_name="usda_market_catalog")
    op.drop_table("usda_market_catalog")
    op.drop_table("usda_market_nutrition_summary")
    op.drop_index("ix_usda_market_food_nutrients_nutrient", table_name="usda_market_food_nutrients")
    op.drop_table("usda_market_food_nutrients")
    op.drop_table("usda_market_nutrients")
    op.drop_index("ix_usda_market_foods_category_name", table_name="usda_market_foods")
    op.drop_table("usda_market_foods")
    op.drop_table("usda_market_categories")
