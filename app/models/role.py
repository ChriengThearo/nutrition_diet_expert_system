from extensions import db
from app.models.associations import tbl_user_roles, tbl_role_permissions

class RoleTable(db.Model):
    __tablename__ = "tbl_roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))

    # Note: matches UserTable.roles
    users = db.relationship("UserTable", secondary=tbl_user_roles, back_populates="roles")

    # Note: matches PermissionTable.roles
    permissions = db.relationship("PermissionTable", secondary=tbl_role_permissions, back_populates="roles")

    def has_permission(self, permission_code: str) -> bool:
        for perm in self.permissions:
            if perm.code == permission_code:
                return True
            if permission_code in perm.get_aliases():
                return True
        return False
    
    def __repr__(self) -> str:
        return f"<Role {self.name}>"
