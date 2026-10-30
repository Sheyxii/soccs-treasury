"""Disposable test databases; never connect to an operational database.

By default each test gets a fresh SQLite file. scripts/test_mysql.py sets TEST_DATABASE_URL
to a throw-away MySQL database; tables are dropped after every test.
"""
import os
import pytest
from flask_migrate import upgrade
from sqlalchemy import text
from app import create_app
from app.extensions import db
from app.models import Role, User
from app.permissions import ROLE_PERMISSIONS

PASSWORD = "Test-password-123!"


@pytest.fixture
def app(tmp_path):
    uri = os.environ.get("TEST_DATABASE_URL") or "sqlite:///" + (tmp_path / "test.sqlite3").as_posix()
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret-key-at-least-32-characters",
        "SQLALCHEMY_DATABASE_URI": uri,
        "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
        "WTF_CSRF_ENABLED": True,
    })
    with application.app_context():
        upgrade()
        for name in ROLE_PERMISSIONS:
            role = Role(name=name)
            user = User(username=name.lower(), full_name=f"Test {name}", role=role)
            user.set_password(PASSWORD)
            db.session.add_all([role, user])
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        if os.environ.get("TEST_DATABASE_URL"):
            db.drop_all()
            with db.engine.begin() as connection:
                connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()
