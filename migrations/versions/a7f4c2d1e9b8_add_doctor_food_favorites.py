"""Add doctor-owned USDA food favorites."""
from alembic import op
import sqlalchemy as sa

revision = "a7f4c2d1e9b8"
down_revision = "f6a2d0b7c3e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tbl_doctor_food_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("fdc_id", sa.Integer(), nullable=False),
        sa.Column("food_name", sa.String(length=255), nullable=False),
        sa.Column("food_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["tbl_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "fdc_id", name="uq_doctor_food_favorite"),
    )


def downgrade():
    op.drop_table("tbl_doctor_food_favorites")
