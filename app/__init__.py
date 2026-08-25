from flask import Flask, redirect, url_for, render_template
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from config import Config
from extensions import db, csrf, login_manager, migrate
from app.models.user import UserTable


def create_app(config_class: type[Config] = Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return UserTable.query.get(int(user_id))

    from app.routes.user_routes import user_bp
    from app.routes.role_routes import role_bp
    from app.routes.permission_routes import permission_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.main_routes import main_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.food_market_routes import food_market_bp

    app.register_blueprint(user_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(food_market_bp)

    @app.errorhandler(OperationalError)
    def handle_db_error(e):
        return render_template("errors/503.html"), 503

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(e):
        return render_template("errors/503.html"), 503

    @app.errorhandler(500)
    def handle_500(e):
        return render_template("errors/503.html"), 500

    with app.app_context():
        try:
            if not app.config.get("SKIP_DB_CREATE_ALL", False):
                db.create_all()
            try:
                from app.services.rbac_service import migrate_permission_codes
                migrate_permission_codes()
            except Exception:
                pass
        except Exception:
            pass
    return app
