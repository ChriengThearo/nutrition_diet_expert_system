import os
from urllib.parse import quote

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _normalize_database_url(raw_url: str | None) -> str | None:
    """Normalize URLs so SQLAlchemy can use both MySQL and Postgres DSNs."""
    if not raw_url:
        return None

    url = raw_url.strip()
    if not url:
        return None

    # Some providers expose "postgres://", but SQLAlchemy expects "postgresql://".
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    # Use psycopg3 explicitly for PostgreSQL connections.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-this")
    SKIP_DB_CREATE_ALL = os.getenv("SKIP_DB_CREATE_ALL", "0") == "1"

    # Database configuration from .env
    DATABASE_URL = _normalize_database_url(
        os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    )
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "mysql")
    DB_NAME = os.environ.get("DB_NAME", "expert_system_test3")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_SCHEMA = os.getenv("DB_SCHEMA")

    # SQLAlchemy configuration
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{quote(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            f"?ssl=true&ssl_verify_cert=false"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set to True for debugging SQL queries
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 2,
        "max_overflow": 1,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }

    if SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        connect_args = {}

        # Supabase requires TLS for direct DB connections.
        if "supabase.co" in SQLALCHEMY_DATABASE_URI and "sslmode=" not in SQLALCHEMY_DATABASE_URI:
            connect_args["sslmode"] = "require"

        # Optional: use a non-public schema as default search_path.
        if DB_SCHEMA:
            connect_args["options"] = f"-csearch_path={DB_SCHEMA},public"

        if connect_args:
            SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = connect_args

    # Security
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
