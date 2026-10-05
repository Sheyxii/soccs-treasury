"""Disposable SQLite tests; never connect to an operational database."""
import pytest
from flask_migrate import upgrade
from app import create_app
from app.extensions import db
from app.models import Role, User
from app.permissions import ROLE_PERMISSIONS

PASSWORD = "Test-password-123!"

@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret-key-at-least-32-characters",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "test.sqlite3").as_posix(),
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
        db.engine.dispose()

@pytest.fixture
def client(app):
    return app.test_client()
