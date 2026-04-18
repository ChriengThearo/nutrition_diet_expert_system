"""add tbl_cooked_foods

Revision ID: e21a4c9d7b3f
Revises: d8e7c1a4f6b9
Create Date: 2026-04-18 17:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e21a4c9d7b3f"
down_revision = "d8e7c1a4f6b9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tbl_cooked_foods" not in inspector.get_table_names():
        op.create_table(
            "tbl_cooked_foods",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("photo", sa.String(length=255), nullable=True),
            sa.Column(
                "is_gevan", sa.Boolean(), server_default=sa.false(), nullable=False
            ),
            sa.Column(
                "food_type",
                sa.String(length=20),
                server_default=sa.text("'cooked'"),
                nullable=False,
            ),
            sa.Column("cooking_method", sa.String(length=80), nullable=True),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("calories", sa.Float(), nullable=True),
            sa.Column("protein", sa.Float(), nullable=True),
            sa.Column("carbs", sa.Float(), nullable=True),
            sa.Column("fat", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        return

    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"] for column in inspector.get_columns("tbl_cooked_foods")
    }
    if "base_food_id" not in existing_columns:
        return

    for foreign_key in inspector.get_foreign_keys("tbl_cooked_foods"):
        fk_name = foreign_key.get("name")
        constrained = set(foreign_key.get("constrained_columns") or [])
        if fk_name and "base_food_id" in constrained:
            op.drop_constraint(fk_name, "tbl_cooked_foods", type_="foreignkey")

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("tbl_cooked_foods")
    }
    if "ix_tbl_cooked_foods_base_food_id" in existing_indexes:
        op.drop_index(
            "ix_tbl_cooked_foods_base_food_id", table_name="tbl_cooked_foods"
        )

    with op.batch_alter_table("tbl_cooked_foods", schema=None) as batch_op:
        batch_op.drop_column("base_food_id")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tbl_cooked_foods" not in inspector.get_table_names():
        return

    existing_indexes = {
        index["name"] for index in inspector.get_indexes("tbl_cooked_foods")
    }
    if "ix_tbl_cooked_foods_base_food_id" in existing_indexes:
        op.drop_index(
            "ix_tbl_cooked_foods_base_food_id", table_name="tbl_cooked_foods"
        )

    op.drop_table("tbl_cooked_foods")
