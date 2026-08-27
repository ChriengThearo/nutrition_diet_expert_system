from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from app.models.user import UserTable


class UserProfileEditForm(FlaskForm):
    """User profile edit form (dashboard user profile)."""

    username = StringField(
        "ឈ្មោះអ្នកប្រើប្រាស់", validators=[DataRequired(), Length(min=3, max=80)]
    )
    full_name = StringField(
        "ឈ្មោះពេញ", validators=[DataRequired(), Length(min=3, max=120)]
    )
    photo = FileField(
        "រូបប្រវត្តិរូប",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "gif"], "អាចផ្ទុកបានតែរូបភាពប៉ុណ្ណោះ!"),
        ],
    )
    current_password = PasswordField(
        "ពាក្យសម្ងាត់បច្ចុប្បន្ន",
        validators=[Optional()],
        render_kw={"autocomplete": "current-password"},
    )
    new_password = PasswordField(
        "ពាក្យសម្ងាត់ថ្មី",
        validators=[Optional(), Length(min=6, max=128)],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "បញ្ជាក់ពាក្យសម្ងាត់ថ្មី",
        validators=[
            Optional(),
            EqualTo("new_password", message="ពាក្យសម្ងាត់ថ្មី និងការបញ្ជាក់ត្រូវតែដូចគ្នា។"),
        ],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("រក្សាទុកការកែប្រែ")

    def __init__(self, original_user: UserTable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_user = original_user

    def validate_username(self, field):
        exists = UserTable.query.filter(
            UserTable.username == field.data,
            UserTable.id != self.original_user.id,
        ).first()
        if exists:
            raise ValidationError("ឈ្មោះអ្នកប្រើប្រាស់នេះត្រូវបានប្រើរួចហើយ។")

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
                "ត្រូវបញ្ចូលពាក្យសម្ងាត់បច្ចុប្បន្ន ដើម្បីប្តូរពាក្យសម្ងាត់។"
            )
            is_valid = False
        elif not self.original_user.check_password(current_password):
            self.current_password.errors.append("ពាក្យសម្ងាត់បច្ចុប្បន្នមិនត្រឹមត្រូវទេ។")
            is_valid = False

        if not new_password:
            self.new_password.errors.append("សូមបញ្ចូលពាក្យសម្ងាត់ថ្មី។")
            is_valid = False
        elif current_password and new_password == current_password:
            self.new_password.errors.append(
                "ពាក្យសម្ងាត់ថ្មីត្រូវតែខុសពីពាក្យសម្ងាត់បច្ចុប្បន្ន។"
            )
            is_valid = False

        if not confirm_password:
            self.confirm_password.errors.append("សូមបញ្ជាក់ពាក្យសម្ងាត់ថ្មីរបស់អ្នក។")
            is_valid = False

        return is_valid


class DoctorProfileEditForm(UserProfileEditForm):
    """Doctor profile edit form: adds doctor-only professional fields."""

    specialty = StringField(
        "ជំនាញឯកទេស", validators=[Optional(), Length(max=120)]
    )
    license_number = StringField(
        "លេខអាជ្ញាប័ណ្ណវេជ្ជសាស្ត្រ", validators=[Optional(), Length(max=60)]
    )
