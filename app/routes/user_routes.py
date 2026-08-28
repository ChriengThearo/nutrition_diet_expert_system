from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from app.forms.user_forms import (
    UserCreateForm,
    UserEditForm,
    UserConfirmDeleteForm,
)
from app.services.user_service import UserService
from app.models.role import RoleTable
from functools import wraps
from app.routes.access_control import permission_required

ROLE_FILTER_LABELS = {
    "doctor": {"title": "Doctors", "subtitle": "Manage doctor accounts on your clinical nutrition platform", "singular": "doctor"},
    "user": {"title": "Patients", "subtitle": "Manage patient accounts on your clinical nutrition platform", "singular": "patient"},
    "admin": {"title": "Administrators", "subtitle": "Manage administrator accounts", "singular": "admin"},
}

user_bp = Blueprint("tbl_users", __name__, url_prefix="/users")


# Admin access decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.has_role("admin"):
            flash("Admin access required to manage users", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


@user_bp.route("/")
@login_required
@admin_required
@permission_required("user.read", "You have no permission to view users.")
def index():
    users = UserService.get_user_all()
    UserService.ensure_default_roles_for_users(users)

    role_filter = (request.args.get("role") or "").strip().lower()
    if role_filter:
        users = [u for u in users if u.has_role(role_filter)]

    role_meta = ROLE_FILTER_LABELS.get(role_filter)
    role_record = None
    if role_filter:
        role_record = RoleTable.query.filter(
            RoleTable.name.ilike(role_filter)
        ).first()

    return render_template(
        "users/index.html",
        users=users,
        role_filter=role_filter,
        role_meta=role_meta,
        role_record=role_record,
    )


@user_bp.route("/<int:user_id>")
@login_required
@admin_required
@permission_required("user.read", "You have no permission to view users.")
def detail(user_id: int):
    user = UserService.get_user_by_id(user_id)
    if user is None:
        abort(404)
    return render_template("users/detail.html", user=user)


@user_bp.route("/create", methods=["GET", "POST"]) 
@login_required
@admin_required
@permission_required("user.create", "You have no permission to create users.")
def create():
    form = UserCreateForm()
    if request.method == "GET":
        preselect_role = (request.args.get("role") or "").strip().lower()
        if preselect_role:
            role_record = RoleTable.query.filter(RoleTable.name.ilike(preselect_role)).first()
            if role_record:
                form.role_id.data = role_record.id
    is_valid = form.validate_on_submit()
    if is_valid:
        data = {
            "username": form.username.data,
            "email": form.email.data,
            "full_name": form.full_name.data,
            "is_active": form.is_active.data,
        }
        password = form.password.data
        role_id = form.role_id.data or None

        user = UserService.create_user(data, password, role_id)
        flash(f"User '{user.username}' was created successfully.", "success")
        created_role = (user.roles[0].name if user.roles else "").strip().lower()
        if created_role in ROLE_FILTER_LABELS:
            return redirect(url_for("tbl_users.index", role=created_role))
        return redirect(url_for("tbl_users.index"))
    if not is_valid and form.is_submitted():
        for field_name, errors in form.errors.items():
            field = getattr(form, field_name, None)
            label = field.label.text if field is not None else field_name
            for error in errors:
                flash(f"{label}: {error}", "danger")

    return render_template("users/create.html", form=form)


@user_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("user.update", "You have no permission to edit users.")
def edit(user_id: int):
    user = UserService.get_user_by_id(user_id)
    if user is None:
        abort(404)

    form = UserEditForm(original_user=user, obj=user)

    if form.validate_on_submit():
        data = {
            "username": form.username.data,
            "email": form.email.data,
            "full_name": form.full_name.data,
            "is_active": form.is_active.data,
        }
        password = form.password.data or None
        role_id = form.role_id.data or None

        UserService.update_user(user, data, password, role_id)
        flash(f"User '{user.username}' was updated successfully.", "success")
        return redirect(url_for("tbl_users.detail", user_id=user.id))

    return render_template("users/edit.html", form=form, user=user)


@user_bp.route("/<int:user_id>/delete", methods=["GET"])
@login_required
@admin_required
@permission_required("user.delete", "You have no permission to delete users.")
def delete_confirm(user_id: int):
    user = UserService.get_user_by_id(user_id)
    if user is None:
        abort(404)

    form = UserConfirmDeleteForm()
    return render_template("users/delete_confirm.html", user=user, form=form)


@user_bp.route("/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
@permission_required("user.delete", "You have no permission to delete users.")
def delete(user_id: int):
    user = UserService.get_user_by_id(user_id)
    if user is None:
        abort(404)

    deleted_role = (user.roles[0].name if user.roles else "").strip().lower()
    UserService.delete_user(user)
    flash("User was deleted successfully.", "success")
    if deleted_role in ROLE_FILTER_LABELS:
        return redirect(url_for("tbl_users.index", role=deleted_role))
    return redirect(url_for("tbl_users.index"))
