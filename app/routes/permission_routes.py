from flask import Blueprint, render_template, abort, redirect, url_for, flash
from app.services.permission_service import PermissionService
from app.forms.permission_forms import (
    PermissionCreateForm,
    PermissionEditForm,
    PermissionConfirmDeleteForm,
)
from app.routes.access_control import permission_required

permission_bp = Blueprint("tbl_permissions", __name__, url_prefix="/permissions")


@permission_bp.route("/")
@permission_required("permission.read", "You have no permission to view permissions.")
def index():
    perms = PermissionService.get_permission_all()
    return render_template("permissions/index.html", permissions=perms)


@permission_bp.route('/create', methods=['GET', 'POST'])
@permission_required("permission.create", "You have no permission to create permissions.")
def create():
    form = PermissionCreateForm()
    if form.validate_on_submit():
        data = {
            'code': form.code.data,
            'name': form.name.data,
            'module': form.module.data,
            'description': form.description.data,
        }
        perm = PermissionService.create_permission(data)
        flash(f"Permission '{perm.code}' created.", 'success')
        return redirect(url_for('tbl_permissions.index'))
    return render_template('permissions/create.html', form=form)


@permission_bp.route("/<int:permission_id>")
@permission_required("permission.read", "You have no permission to view permissions.")
def detail(permission_id: int):
    perm = PermissionService.get_permission_by_id(permission_id)
    if perm is None:
        abort(404)
    return render_template("permissions/detail.html", permission=perm)


@permission_bp.route('/<int:permission_id>/edit', methods=['GET', 'POST'])
@permission_required("permission.edit", "You have no permission to edit permissions.")
def edit(permission_id: int):
    perm = PermissionService.get_permission_by_id(permission_id)
    if perm is None:
        abort(404)
    form = PermissionEditForm(original_permission=perm, obj=perm)
    if form.validate_on_submit():
        data = {'code': form.code.data, 'name': form.name.data, 'module': form.module.data, 'description': form.description.data}
        PermissionService.update_permission(perm, data)
        flash('Permission updated.', 'success')
        return redirect(url_for('tbl_permissions.detail', permission_id=perm.id))
    return render_template('permissions/edit.html', form=form, permission=perm)


@permission_bp.route('/<int:permission_id>/delete', methods=['GET'])
@permission_required("permission.delete", "You have no permission to delete permissions.")
def delete_confirm(permission_id: int):
    perm = PermissionService.get_permission_by_id(permission_id)
    if perm is None:
        abort(404)
    form = PermissionConfirmDeleteForm()
    return render_template('permissions/delete_confirm.html', permission=perm, form=form)


@permission_bp.route('/<int:permission_id>/delete', methods=['POST'])
@permission_required("permission.delete", "You have no permission to delete permissions.")
def delete(permission_id: int):
    perm = PermissionService.get_permission_by_id(permission_id)
    if perm is None:
        abort(404)
    PermissionService.delete_permission(perm)
    flash('Permission deleted.', 'success')
    return redirect(url_for('tbl_permissions.index'))
