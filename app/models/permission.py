import json
from extensions import db
from app.models.associations import tbl_role_permissions

class PermissionTable(db.Model):
    __tablename__ = "tbl_permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    module = db.Column(db.String(80), nullable=False, default="General")
    aliases = db.Column(db.Text)

    # NOTE: matches RoleTable.permissions
    roles = db.relationship("RoleTable", secondary=tbl_role_permissions, back_populates="permissions")

    def get_aliases(self) -> list[str]:
        if not self.aliases:
            return []
        try:
            data = json.loads(self.aliases)
            if isinstance(data, list):
                return [str(item) for item in data if item]
        except Exception:
            pass
        parts = [part.strip() for part in str(self.aliases).split(",")]
        return [part for part in parts if part]

    def set_aliases(self, aliases: list[str]) -> None:
        cleaned = []
        for alias in aliases:
            text = str(alias).strip()
            if text:
                cleaned.append(text)
        unique = sorted(set(cleaned))
        self.aliases = json.dumps(unique) if unique else None

    def __repr__(self) -> str:
        return f"<Permission {self.code}>"
