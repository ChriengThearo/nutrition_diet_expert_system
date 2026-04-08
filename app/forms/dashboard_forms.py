from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from app.models.user import UserTable


class UserProfileEditForm(FlaskForm):
    """User profile edit form (dashboard user profile)."""

    username = StringField(
        "Username", validators=[DataRequired(), Length(min=3, max=80)]
    )
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=3, max=120)]
    )
    photo = FileField(
        "Profile Photo",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "gif"], "Images only!"),
        ],
    )
    current_password = PasswordField(
        "Current Password",
        validators=[Optional()],
        render_kw={"autocomplete": "current-password"},
    )
    new_password = PasswordField(
        "New Password",
        validators=[Optional(), Length(min=6, max=128)],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            Optional(),
            EqualTo("new_password", message="New password and confirmation must match."),
        ],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("Save Changes")

    def __init__(self, original_user: UserTable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_user = original_user

    def validate_username(self, field):
        exists = UserTable.query.filter(
            UserTable.username == field.data,
            UserTable.id != self.original_user.id,
        ).first()
        if exists:
            raise ValidationError("This username is already taken.")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        current_password = self.current_password.data or ""
        new_password = self.new_password.data or ""
        confirm_password = self.confirm_password.data or ""
        wants_password_change = bool(current_password or new_password or confirm_password)

        if not wants_password_change:
            return True

        is_valid = True

        if not current_password:
            self.current_password.errors.append(
                "Current password is required to change your password."
            )
            is_valid = False
        elif not self.original_user.check_password(current_password):
            self.current_password.errors.append("Current password is incorrect.")
            is_valid = False

        if not new_password:
            self.new_password.errors.append("Please enter a new password.")
            is_valid = False
        elif current_password and new_password == current_password:
            self.new_password.errors.append(
                "New password must be different from current password."
            )
            is_valid = False

        if not confirm_password:
            self.confirm_password.errors.append("Please confirm your new password.")
            is_valid = False

        return is_valid
