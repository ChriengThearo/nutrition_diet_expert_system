"""ensure food_type on tbl_foods

Revision ID: aa7e6b4d3f11
Revises: d2a7c4e9f1b8
Create Date: 2026-04-25 09:52:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "aa7e6b4d3f11"
down_revision = "d2a7c4e9f1b8"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tbl_foods" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]: column for column in inspector.get_columns("tbl_foods")
    }

    if "food_type" not in existing_columns:
        with op.batch_alter_table("tbl_foods", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "food_type",
                    sa.String(length=20),
                    server_default=sa.text("'general'"),
                    nullable=False,
                )
            )
    else:
        with op.batch_alter_table("tbl_foods", schema=None) as batch_op:
            batch_op.alter_column(
                "food_type",
                existing_type=sa.String(length=20),
                server_default=sa.text("'general'"),
                nullable=False,
            )

    op.execute(
        sa.text(
            """
            UPDATE tbl_foods
            SET food_type = 'general'
            WHERE food_type IS NULL OR TRIM(food_type) = ''
            """
        )
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "tbl_foods" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("tbl_foods")}
    if "food_type" in existing_columns:
        with op.batch_alter_table("tbl_foods", schema=None) as batch_op:
            batch_op.drop_column("food_type")
