from app.forms.user_forms import UserCreateForm, UserEditForm, UserConfirmDeleteForm
from app.forms.role_forms import RoleCreateForm, RoleEditForm, RoleConfirmDeleteForm
from app.forms.permission_forms import (
    PermissionCreateForm,
    PermissionEditForm,
    PermissionConfirmDeleteForm,
)
from app.forms.diet_rule_forms import DietRuleForm
from app.forms.dashboard_forms import UserProfileEditForm

__all__ = [
    "UserCreateForm",
    "UserEditForm",
    "UserConfirmDeleteForm",
    "RoleCreateForm",
    "RoleEditForm",
    "RoleConfirmDeleteForm",
    "PermissionCreateForm",
    "PermissionEditForm",
    "PermissionConfirmDeleteForm",
    "DietRuleForm",
    "UserProfileEditForm",
]
