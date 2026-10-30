"""Create and configure the SOCCS Treasury application."""
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import RLock
from dotenv import load_dotenv
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from sqlalchemy import text
from werkzeug.exceptions import HTTPException
from config import Config, environment_settings
from app.extensions import csrf, db, login_manager, migrate

# Content Security Policy: everything is served locally; no inline scripts are used.
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
PUBLIC_ENDPOINTS = (None, "auth.login", "static", "health")


def create_app(test_config=None):
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(environment_settings())
    if test_config is not None:
        app.config.update(test_config)
    if str(app.config["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}  # SQLite has no connection pool settings
    if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters in .env.")
    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        hops = app.config["TRUST_PROXY"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops, x_prefix=hops)
    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    from app.models import User, record_audit

    # One Waitress process serves the office. Serialize database requests so backups, restores
    # and posting workflows cannot interleave; database constraints still guard every write.
    office_lock = RLock()

    @app.before_request
    def lock_office_database():
        if request.endpoint not in ('static', 'health'):
            office_lock.acquire()
            g.office_locked = True

    @app.teardown_request
    def unlock_office_database(error=None):
        if g.pop('office_locked', False):
            db.session.remove()
            office_lock.release()

    @login_manager.user_loader
    def load_user(token):
        return db.session.scalar(db.select(User).where(User.session_token == token, User.active.is_(True)))

    @app.before_request
    def enforce_session():
        if request.endpoint in ("static", "health"):
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
        if not current_user.is_authenticated and request.endpoint not in PUBLIC_ENDPOINTS:
            return login_manager.unauthorized()

    csrf.init_app(app)
    from app.auth import bp as auth_bp
    from app.main import bp as main_bp
    from app.users import bp as users_bp
    from app.finance import bp as finance_bp
    from app.backups import bp as backups_bp, automatic_backup
    for blueprint in (auth_bp, main_bp, users_bp, finance_bp, backups_bp):
        app.register_blueprint(blueprint)

    @app.get('/health')
    def health():
        """Liveness/readiness check for a process monitor or reverse proxy. Reveals no data."""
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify(status='ok')
        except Exception:
            app.logger.exception('Health check failed')
            return jsonify(status='database unavailable'), 503
    csrf.exempt(health)

    @app.before_request
    def maintain_backups():
        if current_user.is_authenticated and request.method == 'GET' and request.endpoint != 'static':
            automatic_backup()

    def asset_version():
        # Changes whenever a stylesheet or script is edited, so browsers never keep a stale copy.
        static = Path(app.static_folder)
        return str(int(max((p.stat().st_mtime for p in [*static.glob('css/*.css'), *static.glob('js/*.js')]), default=0)))

    @app.context_processor
    def treasury_context():
        from app.finance.services import today, has_authority
        return dict(office_today=today(), has_authority=has_authority, asset_version=asset_version(),
                    backup_error=app.extensions.get('backup_error', False))

    @app.template_filter('money')
    def format_money(value):
        return f'₱{value or 0:,.2f}'

    from app.finance.words import peso_words
    app.add_template_filter(peso_words, 'peso_words')

    @app.template_filter('localtime')
    def localtime(value):
        from datetime import timedelta
        return (value + timedelta(hours=8)).strftime('%d %b %Y, %I:%M %p') if value else '—'

    from app.cli import register_commands
    register_commands(app)
    register_error_pages(app)

    @app.after_request
    def security_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers.setdefault("Content-Security-Policy", CSP)
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response
    return app


ERROR_PAGES = {
    400: ('Check your request', 'Something in that request was not valid. Go back and try again.'),
    403: ('Access denied', 'Your role does not have permission to open this page.'),
    404: ('Page not found', 'This page or record does not exist. It may have been removed.'),
    405: ('Action not allowed', 'That action cannot be done from this page. Use the buttons on the page instead.'),
    413: ('File too large', 'Use a backup file smaller than 50 MB.'),
    500: ('Something went wrong', 'The system could not finish that request, and nothing was saved. Try again; if it keeps happening, tell the system custodian the time it happened.'),
}


def register_error_pages(app):
    def render(code, message=None):
        title, default = ERROR_PAGES.get(code, ERROR_PAGES[500])
        return render_template('errors/error.html', code=code, title=title, message=message or default), code

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code not in ERROR_PAGES:
            return error
        # 400s from abort(400, 'reason') carry a useful description; others use the friendly default.
        message = error.description if error.code == 400 and error.description and not error.description.startswith('The browser') else None
        return render(error.code, message)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("errors/error.html", code=400, title="Form expired",
                               message="This form was open too long or was submitted twice. Reload the page and submit it again."), 400

    @app.errorhandler(Exception)
    def unexpected_error(error):
        db.session.rollback()
        app.logger.exception('Unhandled error on %s %s', request.method, request.path)
        if app.testing and app.config.get('PROPAGATE_TEST_ERRORS', True):
            raise error
        return render(500)


def configure_logging(app):
    """Write warnings and errors to instance/logs/treasury.log (rotated at 1 MB, 5 files kept)."""
    level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'), logging.INFO)
    app.logger.setLevel(level)
    if app.testing or any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        return
    try:
        folder = Path(app.instance_path) / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / 'treasury.log', maxBytes=1_000_000, backupCount=5, encoding='utf-8')
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        app.logger.addHandler(handler)
    except OSError:
        app.logger.warning('File logging is unavailable; logging to the console only.')
