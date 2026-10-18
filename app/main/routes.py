"""Authenticated home and read-only foundation audit history."""
from flask import render_template, request
from flask_login import login_required, current_user
from app.extensions import db
from app.main import bp
from app.models import AuditLog
from app.permissions import permission_required

@bp.get("/")
@login_required
def index():
    from app.finance.reports import dashboard_data
    from app.models import Transaction
    if current_user.has_permission('dashboard.view') or current_user.has_permission('reports.view'):
        return render_template('main/index.html', **dashboard_data())
    entries = db.session.scalars(db.select(Transaction).where(Transaction.requester_id == current_user.id).order_by(Transaction.id.desc()).limit(8)).all()
    return render_template('main/coordinator.html', transactions=entries)

@bp.get("/audit")
@permission_required("audit.view")
def audit():
    page = max(1, request.args.get("page", 1, type=int))
    stmt = db.select(AuditLog)
    q = request.args.get('q', '').strip()[:120]
    if q:
        stmt = stmt.where(db.or_(AuditLog.actor.contains(q, autoescape=True), AuditLog.action.contains(q, autoescape=True), AuditLog.record.contains(q, autoescape=True)))
    entries = db.paginate(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), page=page, per_page=25, error_out=False)
    return render_template("main/audit.html", entries=entries)
