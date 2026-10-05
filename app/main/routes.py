"""Authenticated home and read-only foundation audit history."""
from flask import render_template, request
from flask_login import login_required
from app.extensions import db
from app.main import bp
from app.models import AuditLog
from app.permissions import permission_required

@bp.get("/")
@login_required
def index():
    return render_template("main/index.html")

@bp.get("/audit")
@permission_required("audit.view")
def audit():
    page = max(1, request.args.get("page", 1, type=int))
    entries = db.paginate(db.select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), page=page, per_page=25, error_out=False)
    return render_template("main/audit.html", entries=entries)
