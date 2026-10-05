"""Create and configure the SOCCS Treasury application."""
import time
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from config import Config, environment_settings
from app.extensions import csrf, db, login_manager, migrate

def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(environment_settings())
    if test_config is not None:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters in .env.")
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    from app.models import User, record_audit

    @login_manager.user_loader
    def load_user(token):
        return db.session.scalar(db.select(User).where(User.session_token == token, User.active.is_(True)))

    @app.before_request
    def enforce_session():
        if request.endpoint == "static":
            return
        if current_user.is_authenticated:
            now = time.time()
            previous = session.get("last_activity", 0)
            if now - previous >= app.permanent_session_lifetime.total_seconds():
                record_audit("session.expired", current_user)
                db.session.commit()
                logout_user()
                session.clear()
                flash("Your session expired. Please sign in again.", "info")
                return redirect(url_for("auth.login"))
            session["last_activity"] = now
        elif session.get("_user_id"):
            session.clear()
        if not current_user.is_authenticated and request.endpoint not in (None, "auth.login", "static"):
            return login_manager.unauthorized()

    csrf.init_app(app)
    from app.auth import bp as auth_bp
    from app.main import bp as main_bp
    from app.users import bp as users_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(users_bp)
    from app.cli import register_commands
    register_commands(app)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/error.html", title="Access denied", message="Your role does not have permission to access this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/error.html", title="Page not found", message="The requested page could not be found."), 404

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("errors/error.html", title="Form expired", message="Reload the page and submit the form again."), 400

    @app.after_request
    def security_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
    return app
