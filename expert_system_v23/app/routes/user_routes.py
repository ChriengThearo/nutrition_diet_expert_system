from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.forms.user_forms import (
    UserCreateForm,
    UserEditForm,
    UserConfirmDeleteForm,
)
from app.services.user_service import UserService
from functools import wraps
from app.routes.access_control import permission_required

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
    return render_template("users/index.html", users=users)


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
@permission_required("user.edit", "You have no permission to edit users.")
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

    UserService.delete_user(user)
    flash("User was deleted successfully.", "success")
    return redirect(url_for("tbl_users.index"))
