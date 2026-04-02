from typing import List, Optional
from app.models.user import UserTable
from app.models.role import RoleTable
from extensions import db
from sqlalchemy import func

class UserService:
    @staticmethod
    def _get_role_by_name(role_name: str) -> Optional[RoleTable]:
        return db.session.scalar(
            db.select(RoleTable).filter(func.lower(RoleTable.name) == role_name.lower())
        )

    @staticmethod
    def _ensure_default_role() -> RoleTable:
        role = UserService._get_role_by_name("user")
        if not role:
            role = RoleTable(name="user", description="User")
            db.session.add(role)
            db.session.flush()
        return role

    @staticmethod
    def get_user_all() -> List[UserTable]:
        return UserTable.query.order_by(UserTable.id.desc()).all()
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[UserTable]:
        return UserTable.query.get(user_id)
    
    @staticmethod
    def create_user(
        data: dict,
        password: str,
        role_id: Optional[int] = None,
        ) -> UserTable:
        user = UserTable(
            username = data["username"],
            email = data["email"],
            full_name = data["full_name"],
            is_active = data.get("is_active", True),
        )
        user.set_password(password)

        db.session.add(user)
        db.session.flush()

        role = db.session.get(RoleTable, role_id) if role_id else None
        if not role:
            role = UserService._ensure_default_role()
        user.roles = [role]

        db.session.commit()
        return user
    
    @staticmethod
    def update_user(
        user: UserTable,
        data: dict, 
        password: Optional[str] = None,
        role_id: Optional[int] = None,
        ) -> UserTable:
        user.username = data["username"]
        user.email = data["email"]
        user.full_name = data["full_name"]
        user.is_active = data.get("is_active", True)

        if password:
            user.set_password(password)

        if role_id:
            role = db.session.get(RoleTable, role_id)
            if role:
                user.roles = [role]

        db.session.commit()
        return user

    @staticmethod
    def ensure_default_roles_for_users(users: List[UserTable]) -> int:
        missing = [user for user in users if not user.roles]
        if not missing:
            return 0
        role = UserService._ensure_default_role()
        for user in missing:
            user.roles = [role]
        db.session.commit()
        return len(missing)
    
    @staticmethod
    def delete_user(user: UserTable) -> None:
        db.session.delete(user)
        db.session.commit()

    
