"""Add doctor patients, consultations, notifications tables and permissions."""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "b3f7a1c8d245"
down_revision = "681540366d00"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("patient.read", "View Patients", "Permission to view assigned patients", "Patient"),
    ("patient.assign", "Assign Patients", "Permission to assign a patient to a doctor", "Patient"),
    ("patient.remove", "Remove Patients", "Permission to unassign a patient from a doctor", "Patient"),
    ("consultation.read", "View Consultations", "Permission to view consultations", "Consultation"),
    ("consultation.create", "Create Consultations", "Permission to log a new consultation", "Consultation"),
    ("consultation.update", "Update Consultations", "Permission to edit a consultation", "Consultation"),
    ("consultation.delete", "Delete Consultations", "Permission to delete a consultation", "Consultation"),
    ("notification.read", "View Notifications", "Permission to view notifications", "Notification"),
    ("notification.update", "Update Notifications", "Permission to mark notifications as read", "Notification"),
]

# permission codes granted to each role_id
ROLE_GRANTS = {
    1: [p[0] for p in NEW_PERMISSIONS],  # doctor: all of them
    2: ["patient.read", "consultation.read"],  # admin: read visibility
}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    permissions_columns = {col["name"] for col in inspector.get_columns("tbl_permissions")}
    if "aliases" not in permissions_columns:
        op.add_column("tbl_permissions", sa.Column("aliases", sa.Text(), nullable=True))

    op.create_table(
        "tbl_doctor_patients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["tbl_users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["tbl_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "patient_id", name="uq_doctor_patient"),
    )

    op.create_table(
        "tbl_consultations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["tbl_users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["tbl_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tbl_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["tbl_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    bind = op.get_bind()

    permissions_table = sa.table(
        "tbl_permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("module", sa.String),
        sa.column("aliases", sa.Text),
    )
    role_permissions_table = sa.table(
        "tbl_role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    # The permissions table has been seeded via raw JSON restores with explicit
    # ids in the past, which can leave the auto-increment sequence behind the
    # actual max id. Re-sync it before inserting to avoid a duplicate-key error.
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('tbl_permissions', 'id'), "
                "COALESCE((SELECT MAX(id) FROM tbl_permissions), 1))"
            )
        )

    existing_codes = {
        row[0]
        for row in bind.execute(sa.select(permissions_table.c.code)).fetchall()
    }
    rows_to_insert = [
        {
            "code": code,
            "name": name,
            "description": description,
            "module": module,
            "aliases": None,
        }
        for code, name, description, module in NEW_PERMISSIONS
        if code not in existing_codes
    ]
    if rows_to_insert:
        op.bulk_insert(permissions_table, rows_to_insert)

    code_to_id = dict(
        bind.execute(
            sa.select(permissions_table.c.code, permissions_table.c.id).where(
                permissions_table.c.code.in_([p[0] for p in NEW_PERMISSIONS])
            )
        ).fetchall()
    )

    existing_grants = set(
        bind.execute(sa.select(role_permissions_table.c.role_id, role_permissions_table.c.permission_id)).fetchall()
    )
    roles_table = sa.table("tbl_roles", sa.column("id", sa.Integer))
    existing_role_ids = {
        row[0] for row in bind.execute(sa.select(roles_table.c.id)).fetchall()
    }
    grant_rows = []
    for role_id, codes in ROLE_GRANTS.items():
        if role_id not in existing_role_ids:
            # Roles table isn't populated yet (e.g. fresh DB migrated before
            # seed data is loaded) - nothing to attach these grants to yet.
            continue
        for code in codes:
            permission_id = code_to_id.get(code)
            if permission_id is None:
                continue
            if (role_id, permission_id) in existing_grants:
                continue
            grant_rows.append({"role_id": role_id, "permission_id": permission_id})
    if grant_rows:
        op.bulk_insert(role_permissions_table, grant_rows)


def downgrade():
    bind = op.get_bind()
    permissions_table = sa.table(
        "tbl_permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
    )
    role_permissions_table = sa.table(
        "tbl_role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    codes = [p[0] for p in NEW_PERMISSIONS]
    ids = [
        row[0]
        for row in bind.execute(
            sa.select(permissions_table.c.id).where(permissions_table.c.code.in_(codes))
        ).fetchall()
    ]
    if ids:
        op.execute(
            role_permissions_table.delete().where(
                role_permissions_table.c.permission_id.in_(ids)
            )
        )
        op.execute(permissions_table.delete().where(permissions_table.c.id.in_(ids)))

    op.drop_table("tbl_notifications")
    op.drop_table("tbl_consultations")
    op.drop_table("tbl_doctor_patients")
