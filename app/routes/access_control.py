from functools import wraps
from flask import flash, redirect, url_for, jsonify, request
from flask_login import current_user


def permission_required(
    permission_code: str, message: str | None = None, json_response: bool = False
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Login required", "danger")
                return redirect(url_for("auth.login"))

            if not current_user.has_permission(permission_code):
                readable_code = (
                    permission_code.replace(".", " ").replace("_", " ").strip()
                )
                msg = message or f"You have no permission to {readable_code}."
                if json_response or request.accept_mimetypes.best == "application/json":
                    return jsonify({"success": False, "message": msg}), 403
                flash(msg, "danger")
                return redirect(url_for("main.home"))

            return func(*args, **kwargs)

        return wrapper

    return decorator
