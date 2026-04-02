from typing import List, Optional
from app.models.permission import PermissionTable
from app.services.rbac_service import _build_aliases
from extensions import db

class PermissionService:
    @staticmethod
    def _normalize_code(code: str) -> str:
        normalized = (code or "").strip()
        if not normalized:
            return ""
        normalized = normalized.replace("_", ".")
        normalized = normalized.replace("user.dash.", "user.dashboard.")
        parts = [("read" if part == "view" else part) for part in normalized.split(".")]
        normalized = ".".join(parts)
        return normalized

    @staticmethod
    def get_permission_all() -> List[PermissionTable]:
        return PermissionTable.query.order_by(PermissionTable.code.asc()).all()

    @staticmethod
    def get_permission_by_id(permission_id: int) -> Optional[PermissionTable]:
        return PermissionTable.query.get(permission_id)
    
    @staticmethod
    def create_permission(data: dict) -> PermissionTable:
        normalized_code = PermissionService._normalize_code(data.get("code", ""))
        perm = PermissionTable(
            code=normalized_code,
            name=data["name"],
            module=data.get("module", "General"),
            description=data.get("description") or "",
        )
        alias_set = _build_aliases(normalized_code)
        alias_set.discard(normalized_code)
        perm.set_aliases(sorted(alias_set))
        db.session.add(perm)
        db.session.commit()
        return perm

    @staticmethod
    def update_permission(permission: PermissionTable, data: dict) -> PermissionTable:
        if "code" in data:
            old_code = permission.code
            new_code = PermissionService._normalize_code(data.get("code", ""))
            permission.code = new_code
            alias_set = set(permission.get_aliases())
            alias_set |= _build_aliases(old_code)
            alias_set |= _build_aliases(new_code)
            alias_set.discard(permission.code)
            permission.set_aliases(sorted(alias_set))
        permission.name = data.get('name', permission.name)
        permission.module = data.get('module', permission.module)
        permission.description = data.get('description', permission.description) or ""
        db.session.commit()
        return permission

    @staticmethod
    def delete_permission(permission: PermissionTable) -> None:
        db.session.delete(permission)
        db.session.commit()
