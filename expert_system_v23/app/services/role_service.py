from typing import List, Optional
from app.models.role import RoleTable
from app.models.permission import PermissionTable
from extensions import db

class RoleService:
    @staticmethod
    def get_role_all() -> List[RoleTable]:
        return RoleTable.query.order_by(RoleTable.name.asc()).all()
    
    @staticmethod
    def get_role_by_id(role_id: int) -> Optional[RoleTable]:
        return RoleTable.query.get(role_id)
    
    @staticmethod
    def create_role(data: dict, permission_ids: Optional[List[int]] = None) -> RoleTable:
        role = RoleTable(
            name = data["name"],
            description = data.get("description") or "",
        )

        if permission_ids:
            permissions = db.session.scalars(
                db.select(PermissionTable).filter(
                    PermissionTable.id.in_(permission_ids)
                )
            ).all()
            role.permissions = list(permissions)

        db.session.add(role)
        db.session.commit()
        return role
    
    @staticmethod
    def update_role(role: RoleTable, data: dict, 
                    permission_ids: Optional[List[int]] = None) -> RoleTable:
        role.name = data["name"]
        role.description = data.get("description") or ""
        

        if permission_ids is not None:
            perms: List[PermissionTable] = []
            if permission_ids:
                perms = db.session.scalars(
                    db.select(PermissionTable).filter(
                            PermissionTable.id.in_(permission_ids)
                    )
                ).all()
            role.permissions = list(perms)

        db.session.commit()
        return role
        
    @staticmethod
    def delete_role(role: RoleTable) -> None:
        db.session.delete(role)
        db.session.commit()

