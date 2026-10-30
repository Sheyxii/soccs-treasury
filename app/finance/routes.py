"""Shared route helpers and module registration."""
from functools import wraps
from flask import abort, flash, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from app.extensions import db


def allow(*permissions):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not any(current_user.has_permission(p) for p in permissions):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def save():
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        flash('This record conflicts with an existing student number, payment, reference or category. Check the details before trying again.', 'danger')
        return False


def paginate(stmt, per_page=20):
    return db.paginate(stmt, page=max(1, request.args.get('page', 1, type=int)), per_page=per_page, error_out=False)


from app.finance import members, transactions, budgets, reports, settings  # noqa: E402,F401
