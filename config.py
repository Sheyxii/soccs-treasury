"""Environment-based settings for the local office application."""
import os
from datetime import timedelta
from sqlalchemy import URL

class Config:
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Localhost HTTP; enable for HTTPS.
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MAX_CONTENT_LENGTH = 1024 * 1024

def environment_settings():
    """Read settings on each factory invocation, including CLI and WSGI."""
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        uri = URL.create(
            "mysql+pymysql",
            username=os.environ.get("MYSQL_USER", "soccs_app"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            database=os.environ.get("MYSQL_DATABASE", "soccs_treasury_dev"),
            query={"charset": "utf8mb4"},
        )
    return {"SECRET_KEY": os.environ.get("SECRET_KEY"), "SQLALCHEMY_DATABASE_URI": uri}
