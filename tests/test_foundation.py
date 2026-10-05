"""Behavior tests for authentication, permissions, migrations and account safety."""
import re
import time
from pathlib import Path
import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from app import create_app
from app.extensions import db
from app.models import AuditLog, Role, User
from app.permissions import permission_required
from tests.conftest import PASSWORD

def csrf(client, path="/auth/login"):
    page = client.get(path)
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.text).group(1)

def login(client, role="treasurer", password=PASSWORD, target=""):
    return client.post("/auth/login" + target, data={
        "username": role, "password": password, "csrf_token": csrf(client),
    })

@pytest.mark.parametrize("path", ["/", "/users/me", "/audit"])
def test_requires_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/auth/login" in response.location

@pytest.mark.parametrize("role,allowed", [
    ("coordinator", False), ("treasurer", True), ("auditor", True),
    ("president", False), ("adviser", False),
])
def test_all_roles_audit_access_and_menu(client, role, allowed):
    assert login(client, role).status_code == 302
    home = client.get("/")
    assert home.status_code == 200
    assert ('href="/audit"' in home.text) == allowed
    response = client.get("/audit")
    assert response.status_code == (200 if allowed else 403)
    if not allowed:
        assert "Access denied" in response.text

@pytest.mark.parametrize("role", ["coordinator", "treasurer", "auditor", "president", "adviser"])
def test_financial_permission_boundaries(app, client, role):
    # Exercise the actual decorator on representative future endpoints.
    for permission in ["transactions.review", "expenses.record", "payments.submit", "reports.view", "users.manage", "unknown"]:
        app.add_url_rule("/test/" + permission, permission,
                         permission_required(permission)(lambda: "allowed"))
    login(client, role)
    expected = {
        "coordinator": {"payments.submit"},
        "treasurer": {"transactions.review", "expenses.record", "reports.view"},
        "auditor": {"reports.view"},
        "president": {"reports.view"},
        "adviser": {"reports.view"},
    }[role]
    for permission in ["transactions.review", "expenses.record", "payments.submit", "reports.view", "users.manage", "unknown"]:
        assert client.get("/test/" + permission).status_code == (200 if permission in expected else 403)

@pytest.mark.parametrize("username,password", [("treasurer", "wrong"), ("missing", PASSWORD), ("' OR 1=1 --", PASSWORD)])
def test_invalid_credentials_are_generic(app, client, username, password):
    response = login(client, username, password)
    assert "Invalid username or password." in response.text
    assert client.get("/").status_code == 302
    with app.app_context():
        event = db.session.scalar(db.select(AuditLog).where(AuditLog.action == "login.failed"))
        assert event is not None
        assert password not in repr((event.actor, event.remarks, event.record))

def test_password_hash_and_inactive_account(app, client):
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "treasurer"))
        assert user.password_hash != PASSWORD
        assert user.check_password(PASSWORD)
        user.active = False
        db.session.commit()
    assert "Invalid username or password." in login(client).text

def test_logout_requires_post_and_csrf(client):
    login(client)
    assert client.get("/auth/logout").status_code == 405
    assert client.post("/auth/logout").status_code == 400
    assert client.get("/").status_code == 200
    token = csrf(client, "/users/me")
    assert client.post("/auth/logout", data={"csrf_token": token}).status_code == 302
    assert client.get("/").status_code == 302

def test_login_requires_csrf(client):
    assert client.post("/auth/login", data={"username": "treasurer", "password": PASSWORD}).status_code == 400
    assert client.get("/").status_code == 302

@pytest.mark.parametrize("target", ["https://evil.example", "//evil.example", "/\\evil.example", "/%09/evil.example"])
def test_no_external_login_redirect(client, target):
    response = login(client, target="?next=" + target)
    assert response.location == "/"

def test_local_login_redirect(client):
    assert login(client, target="?next=/users/me").location == "/users/me"

def test_idle_timeout_and_activity_refresh(app, client):
    login(client)
    with client.session_transaction() as session:
        session["last_activity"] = time.time() - 1700
    assert client.get("/").status_code == 200
    with client.session_transaction() as session:
        assert time.time() - session["last_activity"] < 5
        session["last_activity"] = time.time() - 1801
    assert client.get("/").status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(AuditLog).where(AuditLog.action == "session.expired"))

@pytest.mark.parametrize("command", [
    ["set-user-status", "treasurer", "inactive"],
    ["set-user-role", "treasurer", "President"],
    ["reset-password", "treasurer"],
])
def test_cli_changes_revoke_existing_sessions(app, client, command):
    login(client)
    result = app.test_cli_runner().invoke(args=command, input="Replacement-secret-123!\nReplacement-secret-123!\n")
    assert result.exit_code == 0, result.output
    assert client.get("/").status_code == 302

def test_password_change_validation_and_revocation(app, client):
    other = app.test_client()
    login(other)
    login(client)
    def change(old, new, confirm):
        return client.post("/users/me", data={"csrf_token": csrf(client, "/users/me"),
            "current_password": old, "password": new, "confirm": confirm,
            "role": "President", "active": "false"})
    assert "Current password is incorrect" in change("wrong", "New-password-123", "New-password-123").text
    assert "Passwords must match" in change(PASSWORD, "New-password-123", "different").text
    assert "12" in change(PASSWORD, "short", "short").text
    assert change(PASSWORD, "New-password-123", "New-password-123").status_code == 302
    assert client.get("/").status_code == 302
    assert other.get("/").status_code == 302
    assert login(client, password="New-password-123").status_code == 302
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "treasurer"))
        assert user.role.name == "Treasurer" and user.active
        assert db.session.scalar(db.select(AuditLog).where(AuditLog.action == "password.changed"))

def test_cli_provisioning_and_seed_idempotency(app):
    runner = app.test_cli_runner()
    for _ in range(2):
        assert runner.invoke(args=["seed-roles"]).exit_code == 0
    args = ["create-user", "--username", " New.Officer ", "--full-name", "New Officer", "--role", "Coordinator"]
    result = runner.invoke(args=args, input=PASSWORD + "\n" + PASSWORD + "\n")
    assert result.exit_code == 0, result.output
    assert runner.invoke(args=args).exit_code != 0
    assert runner.invoke(args=["create-user", "--username", "bad", "--full-name", "Bad", "--role", "Admin"]).exit_code != 0
    listing = runner.invoke(args=["list-users"])
    assert "new.officer" in listing.output and PASSWORD not in listing.output
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Role.id))) == 5
        event = db.session.scalar(db.select(AuditLog).where(AuditLog.action == "user.created"))
        assert event.actor.startswith("local:")
        assert event.record.startswith("user:")

def test_migration_round_trip(app):
    with app.app_context():
        assert {"roles", "users", "audit_logs"} <= set(inspect(db.engine).get_table_names())
        db.session.remove()
        downgrade(revision="base")
        assert "users" not in inspect(db.engine).get_table_names()
        upgrade()
        assert "users" in inspect(db.engine).get_table_names()
    assert app.test_cli_runner().invoke(args=["seed-roles"]).exit_code == 0
    assert app.test_cli_runner().invoke(args=["check-db"]).exit_code == 0

def test_duplicate_user_rejected_by_database(app):
    with app.app_context():
        source = db.session.scalar(db.select(User).where(User.username == "treasurer"))
        duplicate = User(username=source.username, full_name="Duplicate", role=source.role)
        duplicate.set_password(PASSWORD)
        db.session.add(duplicate)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

def test_missing_secret_fails_early():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"SECRET_KEY": "", "SQLALCHEMY_DATABASE_URI": "sqlite://"})

def test_local_assets_and_security_headers(client):
    page = client.get("/auth/login")
    assert page.headers["Cache-Control"] == "no-store"
    assert page.headers["X-Frame-Options"] == "DENY"
    resources = re.findall(r'(?:src|href)="([^"]+)"', page.text)
    assert not any(url.startswith(("http:", "https:", "//")) for url in resources)
    for url in resources:
        if url.startswith("/static/"):
            with client.get(url) as response:
                assert response.status_code == 200
                assert len(response.data) > 100
    assert Path("app/static/vendor/bootstrap/LICENSE").exists()

def test_no_public_registration_or_audit_mutations(client):
    login(client)
    assert client.get("/auth/register").status_code == 404
    assert client.post("/audit", data={"csrf_token": csrf(client, "/users/me")}).status_code == 405
