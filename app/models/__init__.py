from .user import UserTable
from .role import RoleTable
from .permission import PermissionTable
from .goal import GoalsTable
from .diet_rule import DietRulesTable
from .food import FoodsTable
from .cooked_food import CookedFoodsTable
from .food_group import FoodGroupTable
from .user_result import UserResultsTable
from .doctor_food_favorite import DoctorFoodFavorite
from .doctor_patient import DoctorPatient
from .consultation import Consultation
from .notification import Notification
from .associations import (
    tbl_user_roles,
    tbl_role_permissions,
    tbl_user_goals,
    tbl_goal_diet_rules,
)

__all__ = [
    "UserTable", "RoleTable", "PermissionTable", "GoalsTable", "DietRulesTable",
    "FoodsTable", "CookedFoodsTable", "FoodGroupTable", "UserResultsTable",
    "DoctorFoodFavorite", "DoctorPatient", "Consultation", "Notification",
]
