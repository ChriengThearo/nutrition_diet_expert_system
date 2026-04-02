"""add is_active to diet rules

Revision ID: 9c1f0a3f1b2a
Revises: 81136eeece12
Create Date: 2026-01-29 10:32:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c1f0a3f1b2a"
down_revision = "81136eeece12"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tbl_diet_rules", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )


def downgrade():
    with op.batch_alter_table("tbl_diet_rules", schema=None) as batch_op:
        batch_op.drop_column("is_active")
