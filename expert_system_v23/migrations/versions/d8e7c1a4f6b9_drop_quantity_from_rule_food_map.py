"""drop quantity from rule food map

Revision ID: d8e7c1a4f6b9
Revises: c1f9e0b7a2d4
Create Date: 2026-02-01 19:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8e7c1a4f6b9"
down_revision = "c1f9e0b7a2d4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tbl_rule_food_map", schema=None) as batch_op:
        batch_op.drop_column("quantity")


def downgrade():
    with op.batch_alter_table("tbl_rule_food_map", schema=None) as batch_op:
        batch_op.add_column(sa.Column("quantity", sa.Float(), nullable=True))
