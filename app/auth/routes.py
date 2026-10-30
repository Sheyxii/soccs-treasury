"""Session login and CSRF-protected logout; no public registration."""
import time
from datetime import timedelta
from urllib.parse import urlsplit
from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.auth import bp
from app.auth.forms import LoginForm
from app.extensions import db
from app.models import AuditLog, User, record_audit, utcnow

_DUMMY_HASH = generate_password_hash("unused-login-timing-placeholder")

def safe_next(target):
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    if "\\" in target or any(ord(char) < 32 for char in target):
        return None
    parts = urlsplit(target)
    return target if not parts.netloc and not parts.scheme else None

def locked_out(user):
    """Pause sign-in for an account after repeated wrong passwords since its last successful sign-in."""
    limit = current_app.config["LOGIN_MAX_ATTEMPTS"]
    if limit <= 0:
        return False
    since = utcnow() - timedelta(minutes=current_app.config["LOGIN_LOCK_MINUTES"])
    last_success = db.session.scalar(db.select(db.func.max(AuditLog.created_at)).where(
        AuditLog.user_id == user.id, AuditLog.action.in_(("login.succeeded", "password.reset"))))
    if last_success and last_success > since:
        since = last_success
    failures = db.session.scalar(db.select(db.func.count(AuditLog.id)).where(
        AuditLog.user_id == user.id, AuditLog.action == "login.failed", AuditLog.created_at > since))
    return failures >= limit

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).where(User.username == form.username.data.strip().lower()))
        if user and locked_out(user):
            record_audit("login.blocked", user, remarks="Too many failed attempts")
            db.session.commit()
            flash(f"Too many failed sign-in attempts. Wait {current_app.config['LOGIN_LOCK_MINUTES']} minutes, "
                  "or ask the system custodian to reset your password.", "danger")
            return render_template("auth/login.html", form=form)
        valid_password = check_password_hash(user.password_hash if user else _DUMMY_HASH, form.password.data)
        if user and valid_password and user.is_active:
            session.clear()
            login_user(user)
            session.permanent = True
            session["last_activity"] = time.time()
            record_audit("login.succeeded", user)
            db.session.commit()
            return redirect(safe_next(request.args.get("next")) or url_for("main.index"))
        record_audit("login.failed", user)
        db.session.commit()
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)

@bp.post("/logout")
@login_required
def logout():
    record_audit("logout", current_user)
    db.session.commit()
    logout_user()
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("auth.login"))
