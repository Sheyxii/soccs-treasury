"""Production launcher: python run.py (never enables debug mode).

HOST, PORT and THREADS come from .env. The defaults serve only this computer (127.0.0.1:5000).
Run one process only: backups and posting are serialized inside this process.
"""
import logging
import os
import sys
from waitress import serve
from sqlalchemy.exc import SQLAlchemyError
from app import create_app
from app.extensions import db
from app.models import User


def print_login_details(app):
    """Show available login identities and local password recovery instructions."""
    print("\nSign in with a username (this app does not use email addresses).")
    with app.app_context():
        try:
            usernames = db.session.scalars(
                db.select(User.username).where(User.active.is_(True)).order_by(User.username)
            ).all()
        except SQLAlchemyError:
            db.session.rollback()
            print("Cannot list accounts. Check that MySQL is running and the database is set up.")
        else:
            if usernames:
                print("Available usernames: " + ", ".join(usernames))
            else:
                print("No active accounts. Create an officer account using the README setup instructions.")
    print("Password: the password you set for your account (stored as a hash; cannot be displayed).")
    print("Forgot it? Stop the app and run the following, replacing USERNAME with your username:")
    print(r"  .\.venv\Scripts\python.exe -m flask --app app reset-password USERNAME", flush=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        app = create_app()
    except RuntimeError as error:
        sys.exit(f"Cannot start SOCCS Treasury: {error}")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    threads = int(os.environ.get("THREADS", "8"))
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print_login_details(app)
    print(f"SOCCS Treasury is running at http://{shown}:{port}  (press Ctrl+C to stop)", flush=True)
    # Behind a reverse proxy, set TRUST_PROXY=1 in .env; the app (ProxyFix) then reads X-Forwarded-* headers.
    serve(app, host=host, port=port, threads=threads, ident="SOCCS Treasury")
