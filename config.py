import os
from dotenv import load_dotenv
from urllib.parse import quote

# Load environment variables
load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-this")
    SKIP_DB_CREATE_ALL = os.getenv("SKIP_DB_CREATE_ALL", "0") == "1"

    # Database configuration from .env
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "mysql")
    DB_NAME = os.environ.get("DB_NAME", "expert_system_test3")
    DB_PORT = os.getenv("DB_PORT", "3306")

    # SQLAlchemy configuration
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{quote(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?ssl=true&ssl_verify_cert=false"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False  # Set to True for debugging SQL queries

    # Security
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
