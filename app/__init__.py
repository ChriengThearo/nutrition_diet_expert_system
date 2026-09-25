from flask import Flask, redirect, url_for, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from config import Config
from extensions import db, csrf, login_manager, migrate, oauth
from app.models.user import UserTable


def create_app(config_class: type[Config] = Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Railway (and most PaaS hosts) terminate HTTPS at the edge and forward
    # requests over plain HTTP, so without this Flask builds http:// URLs
    # (e.g. the Google OAuth redirect_uri) instead of https://.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

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
        try:
            # Load CLIP and the bundled USDA text index as soon as the worker
            # starts. This keeps the first user's scan from paying the model
            # startup cost while still allowing the web server to boot first.
            if app.config.get("USDA_SCANNER_WARMUP", True) and not app.config.get("TESTING", False):
                from app.services.local_food_scanner import LocalFoodScanner
                LocalFoodScanner.prepare(app.instance_path)
        except Exception:
            # Scanner readiness is reported by its status endpoint. A scanner
            # failure must not prevent the rest of the dashboard from starting.
            pass
    return app
