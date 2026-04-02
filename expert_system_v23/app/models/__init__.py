from .user import UserTable
from .role import RoleTable
from .permission import PermissionTable
from .goal import GoalsTable
from .diet_rule import DietRulesTable
from .food import FoodsTable
from .user_result import UserResultsTable
from .associations import (
    tbl_user_roles,
    tbl_role_permissions,
    tbl_user_goals,
    tbl_goal_diet_rules,
)

__all__ = [
    "UserTable",
    "RoleTable",
    "PermissionTable",
    "GoalsTable",
    "DietRulesTable",
    "FoodsTable",
    "UserResultsTable",
]
