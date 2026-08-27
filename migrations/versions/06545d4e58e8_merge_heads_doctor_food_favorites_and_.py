"""merge heads: doctor_food_favorites and food_type_ensure

Revision ID: 06545d4e58e8
Revises: a7f4c2d1e9b8, aa7e6b4d3f11
Create Date: 2026-08-27 20:07:34.594941

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '06545d4e58e8'
down_revision = ('a7f4c2d1e9b8', 'aa7e6b4d3f11')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
