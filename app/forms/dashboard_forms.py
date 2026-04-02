from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

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
