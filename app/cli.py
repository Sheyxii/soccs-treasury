"""Trusted local maintenance commands; no web-based role escalation."""
import getpass
import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import AuditLog, Role, User, normalize_username, record_audit
from app.permissions import ROLE_PERMISSIONS

def operator():
    return f"local:{getpass.getuser()}"[:160]

def find_user(username):
    try:
        name = normalize_username(username)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    user = db.session.scalar(db.select(User).where(User.username == name))
    if user is None:
        raise click.ClickException("Officer account not found.")
    return user

def password_prompt(user):
    password = click.prompt("Password (12-128 characters)", hide_input=True, confirmation_prompt=True)
    try:
        user.set_password(password)
    except ValueError as error:
        raise click.ClickException(str(error)) from error

def save():
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise click.ClickException("The account already exists or its role is invalid.") from error

@click.command("seed-roles")
@with_appcontext
def seed_roles():
    """Add the five baseline roles; safe to run more than once."""
    for name in ROLE_PERMISSIONS:
        if not db.session.scalar(db.select(Role).where(Role.name == name)):
            db.session.add(Role(name=name))
            record_audit("role.created", actor=operator(), record=f"role:{name}")
    save()
    click.echo("Five officer roles are ready.")

@click.command("create-user")
@click.option("--username", required=True)
@click.option("--full-name", required=True)
@click.option("--role", type=click.Choice(list(ROLE_PERMISSIONS)), required=True)
@with_appcontext
def create_user(username, full_name, role):
    """Provision an officer; passwords are entered using a hidden prompt."""
    try:
        username = normalize_username(username)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    full_name = full_name.strip()
    if not 1 <= len(full_name) <= 120:
        raise click.ClickException("Full name must contain 1-120 characters.")
    assigned_role = db.session.scalar(db.select(Role).where(Role.name == role))
    if assigned_role is None:
        raise click.ClickException("Run flask --app app seed-roles first.")
    if db.session.scalar(db.select(User).where(User.username == username)):
        raise click.ClickException("That username already exists.")
    user = User(username=username, full_name=full_name, role=assigned_role)
    password_prompt(user)
    db.session.add(user)
    try:
        db.session.flush()
    except IntegrityError as error:
        db.session.rollback()
        raise click.ClickException("That username already exists.") from error
    record_audit("user.created", user, actor=operator(), record=f"user:{user.id}", remarks=f"Role: {role}")
    save()
    click.echo(f"Created {username} ({role}).")

@click.command("list-users")
@with_appcontext
def list_users():
    """List identities and account status without secrets."""
    for user in db.session.scalars(db.select(User).order_by(User.username)):
        click.echo(f"{user.username}\t{user.full_name}\t{user.role.name}\t{'active' if user.active else 'inactive'}")

@click.command("set-user-role")
@click.argument("username")
@click.argument("role", type=click.Choice(list(ROLE_PERMISSIONS)))
@with_appcontext
def set_user_role(username, role):
    """Change role and invalidate existing sessions."""
    user = find_user(username)
    assigned_role = db.session.scalar(db.select(Role).where(Role.name == role))
    if assigned_role is None:
        raise click.ClickException("Run seed-roles first.")
    previous = user.role.name
    user.role = assigned_role
    user.revoke_sessions()
    record_audit("user.role_changed", user, actor=operator(), record=f"user:{user.id}", remarks=f"{previous} -> {role}")
    save()
    click.echo("Role updated; previous sessions revoked.")

@click.command("set-user-status")
@click.argument("username")
@click.argument("status", type=click.Choice(["active", "inactive"]))
@with_appcontext
def set_user_status(username, status):
    """Activate/deactivate an officer and revoke previous sessions."""
    user = find_user(username)
    user.active = status == "active"
    user.revoke_sessions()
    record_audit("user.status_changed", user, actor=operator(), record=f"user:{user.id}", remarks=status)
    save()
    click.echo(f"Account is {status}; previous sessions revoked.")

@click.command("reset-password")
@click.argument("username")
@with_appcontext
def reset_password(username):
    """Reset a forgotten password locally and revoke previous sessions."""
    user = find_user(username)
    password_prompt(user)
    record_audit("password.reset", user, actor=operator(), record=f"user:{user.id}")
    save()
    click.echo("Password reset; previous sessions revoked.")

@click.command("check-db")
@with_appcontext
def check_db():
    """Check connectivity and the migrated foundation schema."""
    count = db.session.scalar(db.select(db.func.count(Role.id)))
    db.session.execute(db.select(User.id).limit(1))
    db.session.execute(db.select(AuditLog.id).limit(1))
    click.echo(f"Database connected; foundation tables available; {count} roles.")

def register_commands(app):
    for command in (seed_roles, create_user, list_users, set_user_role, set_user_status, reset_password, check_db):
        app.cli.add_command(command)
