from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, ValidationError
from app.models.permission import PermissionTable
from extensions import db

BASE_MODULE_CHOICES = [
    "Foods",
    "Rules",
    "Dashboard",
    "Doctor",
    "Users",
]


def _module_choices(current: str | None = None):
    base = list(dict.fromkeys(BASE_MODULE_CHOICES))
    current_value = (current or "").strip()
    if current_value and current_value not in base:
        base.append(current_value)
    return [(name, name) for name in base]


def _normalize_code(code: str) -> str:
    normalized = (code or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("_", ".")
    normalized = normalized.replace("user.dash.", "user.dashboard.")
    parts = [("read" if part == "view" else part) for part in normalized.split(".")]
    normalized = ".".join(parts)
    return normalized


class PermissionCreateForm(FlaskForm):
    code = StringField(
        "Code",
        validators=[DataRequired(), Length(min=2, max=64)],
        render_kw={"placeholder": "e.g. user.read"},
    )

    name = StringField(
        "Name",
        validators=[DataRequired(), Length(min=2, max=120)],
        render_kw={"placeholder": "Human-readable name"},
    )

    module = SelectField(
        "Module",
        choices=[],
        default="Users",
    )

    description = TextAreaField(
        "Description",
        render_kw={"placeholder": "What does this permission allow?"},
    )

    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.module.choices = _module_choices()

    def validate_code(self, field):
        normalized = _normalize_code(field.data)
        exists = db.session.scalar(
            db.select(PermissionTable).filter(PermissionTable.code == normalized)
        )
        if exists:
            raise ValidationError("This permission code is already in use.")

    def validate_name(self, field):
        exists = db.session.scalar(
            db.select(PermissionTable).filter(PermissionTable.name == field.data)
        )
        if exists:
            raise ValidationError("This permission name is already in use.")


class PermissionEditForm(FlaskForm):
    code = StringField(
        "Code",
        validators=[DataRequired(), Length(min=2, max=64)],
    )

    name = StringField(
        "Name",
        validators=[DataRequired(), Length(min=2, max=120)],
    )

    module = SelectField(
        "Module",
        choices=[],
        default="Users",
    )

    description = TextAreaField("Description")

    submit = SubmitField("Update")

    def __init__(self, original_permission: PermissionTable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_permission = original_permission
        self.module.choices = _module_choices(original_permission.module)
        if not self.is_submitted():
            self.module.data = original_permission.module

    def validate_code(self, field):
        normalized = _normalize_code(field.data)
        q = db.select(PermissionTable).filter(
            PermissionTable.code == normalized,
            PermissionTable.id != self.original_permission.id,
        )
        exists = db.session.scalar(q)
        if exists:
            raise ValidationError("This permission code is already in use.")

    def validate_name(self, field):
        q = db.select(PermissionTable).filter(
            PermissionTable.name == field.data,
            PermissionTable.id != self.original_permission.id,
        )
        exists = db.session.scalar(q)
        if exists:
            raise ValidationError("This permission name is already in use.")


class PermissionConfirmDeleteForm(FlaskForm):
    submit = SubmitField("Confirm Delete")
