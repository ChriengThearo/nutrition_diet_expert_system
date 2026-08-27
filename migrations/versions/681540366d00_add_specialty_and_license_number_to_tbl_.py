"""add specialty and license_number to tbl_users

Revision ID: 681540366d00
Revises: 06545d4e58e8
Create Date: 2026-08-27 20:10:00.612767

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '681540366d00'
down_revision = '06545d4e58e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tbl_users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('specialty', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('license_number', sa.String(length=60), nullable=True))


def downgrade():
    with op.batch_alter_table('tbl_users', schema=None) as batch_op:
        batch_op.drop_column('license_number')
        batch_op.drop_column('specialty')
