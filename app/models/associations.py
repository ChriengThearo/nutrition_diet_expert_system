from extensions import db

tbl_user_roles = db.Table(
    "tbl_user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("tbl_users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("tbl_roles.id"), primary_key=True),
)

# role <-> permission (many-to-many)
tbl_role_permissions = db.Table(
    "tbl_role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("tbl_roles.id"), primary_key=True),
    db.Column(
        "permission_id", db.Integer, db.ForeignKey("tbl_permissions.id"), primary_key=True
    ),
)

# user <-> goals (many-to-many)
tbl_user_goals = db.Table(
    "tbl_user_goals",
    db.Column("user_id", db.Integer, db.ForeignKey("tbl_users.id"), primary_key=True),
    db.Column("goal_id", db.Integer, db.ForeignKey("tbl_goals.id"), primary_key=True),
)

# goals <-> diet_rules (many-to-many)
tbl_goal_diet_rules = db.Table(
    "tbl_goal_diet_rules",
    db.Column("goal_id", db.Integer, db.ForeignKey("tbl_goals.id"), primary_key=True),
    db.Column("diet_rule_id", db.Integer, db.ForeignKey("tbl_diet_rules.id"), primary_key=True),
)


