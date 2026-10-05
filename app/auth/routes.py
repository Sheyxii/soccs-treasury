"""Session login and CSRF-protected logout; no public registration."""
import time
from urllib.parse import urlsplit
from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.auth import bp
from app.auth.forms import LoginForm
from app.extensions import db
from app.models import User, record_audit

_DUMMY_HASH = generate_password_hash("unused-login-timing-placeholder")

def safe_next(target):
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    if "\\" in target or any(ord(char) < 32 for char in target):
        return None
    parts = urlsplit(target)
    return target if not parts.netloc and not parts.scheme else None

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(db.select(User).where(User.username == form.username.data.strip().lower()))
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
