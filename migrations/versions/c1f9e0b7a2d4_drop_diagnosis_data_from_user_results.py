"""drop diagnosis_data from user results

Revision ID: c1f9e0b7a2d4
Revises: a5c8d2f1b9e7
Create Date: 2026-02-01 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1f9e0b7a2d4"
down_revision = "a5c8d2f1b9e7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tbl_user_results", schema=None) as batch_op:
        batch_op.drop_column("diagnosis_data")


def downgrade():
    with op.batch_alter_table("tbl_user_results", schema=None) as batch_op:
        batch_op.add_column(sa.Column("diagnosis_data", sa.Text(), nullable=True))
