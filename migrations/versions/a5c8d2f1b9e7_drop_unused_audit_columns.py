"""drop unused audit columns

Revision ID: a5c8d2f1b9e7
Revises: f6a2d0b7c3e1
Create Date: 2026-02-01 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a5c8d2f1b9e7"
down_revision = "f6a2d0b7c3e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tbl_roles", schema=None) as batch_op:
        batch_op.drop_column("created_at")
        batch_op.drop_column("updated_at")

    with op.batch_alter_table("tbl_permissions", schema=None) as batch_op:
        batch_op.drop_column("created_at")
        batch_op.drop_column("updated_at")

    with op.batch_alter_table("tbl_goals", schema=None) as batch_op:
        batch_op.drop_column("created_at")

    with op.batch_alter_table("tbl_rule_food_map", schema=None) as batch_op:
        batch_op.drop_column("created_at")
        batch_op.drop_column("updated_at")

    with op.batch_alter_table("tbl_user_results", schema=None) as batch_op:
        batch_op.drop_column("updated_at")


def downgrade():
    with op.batch_alter_table("tbl_user_results", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    with op.batch_alter_table("tbl_rule_food_map", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    with op.batch_alter_table("tbl_goals", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    with op.batch_alter_table("tbl_permissions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )

    with op.batch_alter_table("tbl_roles", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
