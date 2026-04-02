from collections import defaultdict
from flask_wtf import FlaskForm
from wtforms import TextAreaField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError
from app.models import RoleTable, PermissionTable
from extensions import db
from app.forms.multi_checkbox_field import MultiCheckboxField


def _permission_choices():
    perms = db.session.scalars(
        db.select(PermissionTable).order_by(PermissionTable.code)
    ).all()
    return [(perm.id, f"{perm.code} - {perm.name}") for perm in perms]


def _permission_grouped_by_module():
    """
    Return permissions grouped by their module:
    {
        "User": [Permission, ...],
        "Role": [Permission, ...],
        ...
    }
    """
    perms = db.session.scalars(
        db.select(PermissionTable).order_by(
            PermissionTable.module, PermissionTable.code
        )
    ).all()
    grouped = defaultdict(list)
    for perm in perms:
        module = (perm.module or "General").strip() or "General"
        grouped[module].append(perm)
    return dict(grouped)


class RoleCreateForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(min=2, max=80)],
        render_kw={"placeholder": "Role name"},
    )

    description = TextAreaField(
        "Description",
        render_kw={"placeholder": "Short description (optional)"},
    )

    permission_ids = MultiCheckboxField(
        "Permissions",
        coerce=int,
        render_kw={"placeholder": "Permissions granted to this role"},
    )

    submit = SubmitField("Save")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.permission_ids.choices = _permission_choices()

    @property
    def permissions_by_module(self):
        return _permission_grouped_by_module()

    def validate_name(self, field):
        exsists = db.session.scalar(
            db.select(RoleTable).filter(RoleTable.name == field.data)
        )
        if exsists:
            raise ValidationError("This role name is already taken.")


class RoleEditForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(min=2, max=80)],
    )
    description = TextAreaField("Description")

    permission_ids = MultiCheckboxField(
        "Permissions",
        coerce=int,
    )

    submit = SubmitField("Update")

    def __init__(self, original_role: RoleTable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_role = original_role
        self.permission_ids.choices = _permission_choices()

        if not self.is_submitted():
            self.permission_ids.data = [p.id for p in original_role.permissions]

    @property
    def permissions_by_module(self):
        return _permission_grouped_by_module()

    def validate_name(self, field):
        q = db.select(RoleTable).filter(
            RoleTable.name == field.data,
            RoleTable.id != self.original_role.id,
        )
        exists = db.session.scalar(q)
        if exists:
            raise ValidationError("This role name is already taken.")


class RoleConfirmDeleteForm(FlaskForm):
    submit = SubmitField("Delete Role")
