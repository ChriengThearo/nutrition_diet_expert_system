"""remove disease and file upload tables

Revision ID: f6a2d0b7c3e1
Revises: c7a1a9faad95
Create Date: 2026-02-01 09:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6a2d0b7c3e1"
down_revision = "c7a1a9faad95"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("tbl_user_diseases")
    op.drop_table("tbl_disease_diet_rules")
    op.drop_table("tbl_file_uploads")
    op.drop_table("tbl_diseases")


def downgrade():
    op.create_table(
        "tbl_diseases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tbl_disease_diet_rules",
        sa.Column("disease_id", sa.Integer(), nullable=False),
        sa.Column("diet_rule_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["diet_rule_id"], ["tbl_diet_rules.id"]),
        sa.ForeignKeyConstraint(["disease_id"], ["tbl_diseases.id"]),
        sa.PrimaryKeyConstraint("disease_id", "diet_rule_id"),
    )
    op.create_table(
        "tbl_user_diseases",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("disease_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["disease_id"], ["tbl_diseases.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["tbl_users.id"]),
        sa.PrimaryKeyConstraint("user_id", "disease_id"),
    )
    op.create_table(
        "tbl_file_uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("processing_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by"], ["tbl_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
