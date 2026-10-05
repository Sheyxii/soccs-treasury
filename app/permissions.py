"""Deny-by-default authorization policy for five officer roles.

Financial permissions define boundaries for future modules, not implemented
financial functionality. No officer receives account-administration rights.
"""
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

ROLE_PERMISSIONS = {
    "Coordinator": frozenset({"members.manage", "payments.submit", "expenses.submit", "requests.view_own"}),
    "Treasurer": frozenset({"members.manage", "payments.record", "payments.verify", "transactions.review", "budgets.manage", "income.record", "expenses.record", "dashboard.view", "reports.view", "audit.view"}),
    "Auditor": frozenset({"payments.verify", "financial_records.view", "budgets.view", "reports.view", "audit.view"}),
    "President": frozenset({"dashboard.view", "reports.view"}),
    "Adviser": frozenset({"dashboard.view", "reports.view"}),
}

def permission_required(permission):
    def decorate(view):
        @wraps(view)
        @login_required
        def protected(*args, **kwargs):
            if not current_user.has_permission(permission):
                abort(403)
            return view(*args, **kwargs)
        return protected
    return decorate
