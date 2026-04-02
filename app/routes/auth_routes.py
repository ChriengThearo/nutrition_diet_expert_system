from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from app.models.user import UserTable
from app.models.role import RoleTable
from app.services.user_service import UserService
from app.services.rbac_service import sync_rbac
from extensions import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = UserTable.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash(
                    "Your account is inactive. Please contact administrator.", "warning"
                )
                return redirect(url_for("auth.login"))

            login_user(user)
            sync_rbac()
            flash("Logged in successfully.", "success")

            # Ensure the special Admin account has admin role
            if user.username.strip().lower() == "admin":
                admin_role = RoleTable.query.filter_by(name="admin").first()
                if not admin_role:
                    admin_role = RoleTable.query.filter_by(name="Admin").first()
                if not admin_role:
                    admin_role = RoleTable(name="admin", description="Administrator")
                    db.session.add(admin_role)
                    db.session.commit()
                if admin_role not in user.roles:
                    user.roles.append(admin_role)
                    db.session.commit()

            # Ensure the special Doctor account has doctor role
            if user.username.strip().lower() == "doctor":
                doctor_role = RoleTable.query.filter_by(name="doctor").first()
                if not doctor_role:
                    doctor_role = RoleTable.query.filter_by(name="Doctor").first()
                if not doctor_role:
                    doctor_role = RoleTable(name="doctor", description="Doctor")
                    db.session.add(doctor_role)
                    db.session.commit()
                if doctor_role not in user.roles:
                    user.roles.append(doctor_role)
                    db.session.commit()
                return redirect(url_for("dashboard.doctor_dashboard"))

            # Redirect based on user role
            if user.has_role("admin"):
                return redirect(url_for("dashboard.admin_dashboard"))
            elif user.has_role("doctor"):
                return redirect(url_for("dashboard.doctor_dashboard"))
            else:
                return redirect(url_for("dashboard.user_dashboard"))

        flash("Invalid username or password.", "danger")
        return redirect(url_for("auth.login"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors: list[str] = []

        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not full_name:
            errors.append("Full_name is required.")
        if not password:
            errors.append("Password is required.")
        if password and password != confirm_password:
            errors.append("Passwords do not match.")

        if username and UserTable.query.filter_by(username=username).first():
            errors.append("This username is already taken.")
        if email and UserTable.query.filter_by(email=email).first():
            errors.append("This email is already registered.")

        if errors:
            for msg in errors:
                flash(msg, "danger")
            return render_template(
                "auth/register.html",
                username=username,
                email=email,
                full_name=full_name,
            )

        default_role = RoleTable.query.filter_by(name="user").first()
        default_role_id = default_role.id if default_role else None

        data = {
            "username": username,
            "email": email,
            "full_name": full_name,
            "is_active": True,
        }

        new_user = UserService.create_user(
            data=data,
            password=password,
            role_id=default_role_id,
        )

        sync_rbac()
        login_user(new_user)
        flash("Account created successfully. You are now logged in.", "success")

        # Redirect based on user role
        if new_user.has_role("admin"):
            return redirect(url_for("dashboard.admin_dashboard"))
        elif new_user.has_role("doctor"):
            return redirect(url_for("dashboard.doctor_dashboard"))
        else:
            return redirect(url_for("dashboard.user_dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
