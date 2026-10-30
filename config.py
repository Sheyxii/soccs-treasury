"""Environment-based settings. Defaults suit the single office PC; .env overrides them for other deployments."""
import os
from datetime import timedelta
from sqlalchemy import URL


def env_flag(name, default=False):
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    WTF_CSRF_TIME_LIMIT = None  # tokens live as long as the session (sessions already expire after inactivity)


def environment_settings():
    """Read settings on each factory invocation, including CLI and WSGI."""
    uri = os.environ.get("DATABASE_URL")
    if not uri:
        uri = URL.create(
            "mysql+pymysql",
            username=os.environ.get("MYSQL_USER", "soccs_app"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=env_int("MYSQL_PORT", 3306),
            database=os.environ.get("MYSQL_DATABASE", "soccs_treasury_dev"),
            query={"charset": "utf8mb4"},
        )
    engine = {"pool_pre_ping": True}
    if not str(uri).startswith("sqlite"):
        engine.update(pool_recycle=env_int("DB_POOL_RECYCLE", 1800), pool_size=env_int("DB_POOL_SIZE", 5))
    secure = env_flag("SESSION_COOKIE_SECURE")  # turn on when served over HTTPS
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": uri,
        "SQLALCHEMY_ENGINE_OPTIONS": engine,
        "SESSION_COOKIE_SECURE": secure,
        "REMEMBER_COOKIE_SECURE": secure,
        "PREFERRED_URL_SCHEME": "https" if secure else "http",
        "PERMANENT_SESSION_LIFETIME": timedelta(minutes=env_int("SESSION_TIMEOUT_MINUTES", 30)),
        "TRUST_PROXY": env_int("TRUST_PROXY", 0),  # number of reverse proxies in front (0 = none)
        "LOGIN_MAX_ATTEMPTS": env_int("LOGIN_MAX_ATTEMPTS", 5),
        "LOGIN_LOCK_MINUTES": env_int("LOGIN_LOCK_MINUTES", 15),
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO").upper(),
    }
