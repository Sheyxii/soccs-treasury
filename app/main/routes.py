"""Authenticated home and read-only foundation audit history."""
from flask import abort, render_template, request
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

def search_scope(user):
    """What the global search may show this officer: members and/or a transaction query."""
    from app.finance.services import has_authority
    from app.models import Transaction
    members = user.has_permission('members.manage') or user.has_permission('payments.verify')
    stmt = None
    if user.has_permission('transactions.review') or user.has_permission('financial_records.view'):
        stmt = db.select(Transaction)
    else:
        clauses = []
        if user.has_permission('requests.view_own'):
            clauses.append(Transaction.requester_id == user.id)
        if has_authority(user, 'overspend'):
            clauses.append(Transaction.overspend.is_(True))
        if clauses:
            stmt = db.select(Transaction).where(db.or_(*clauses))
    return members, stmt


@bp.app_context_processor
def search_context():
    if not current_user.is_authenticated:
        return {}
    members, stmt = search_scope(current_user)
    return {'can_search': members or stmt is not None}


def search_terms(q):
    """Split the query into words; every word must match somewhere (so "juan cruz" finds "Juan Dela Cruz")."""
    return [word for word in q.split() if word][:6]


def find_matches(q, member_limit, transaction_limit):
    from app.models import Member, Transaction
    can_members, stmt = search_scope(current_user)
    if not can_members and stmt is None:
        abort(403)
    terms = search_terms(q)
    members, transactions = [], []
    if terms and can_members:
        member_stmt = db.select(Member)
        for word in terms:
            member_stmt = member_stmt.where(db.or_(
                Member.full_name.contains(word, autoescape=True), Member.student_number.contains(word, autoescape=True),
                Member.section.contains(word, autoescape=True), Member.program == word.upper()))
        # Names that start with the query come first, then alphabetical.
        member_stmt = member_stmt.order_by(db.case((Member.full_name.startswith(q, autoescape=True), 0), else_=1), Member.full_name)
        members = db.session.scalars(member_stmt.limit(member_limit)).all()
    if terms and stmt is not None:
        for word in terms:
            clauses = [Transaction.description.contains(word, autoescape=True), Transaction.member_name.contains(word, autoescape=True),
                       Transaction.student_number.contains(word, autoescape=True), Transaction.reference.contains(word, autoescape=True),
                       Transaction.kind == word.title(), Transaction.status == word.title()]
            number = word.upper().removeprefix('TXN-')
            if number.isdigit() and len(number) < 10:
                clauses.append(Transaction.id == int(number))
            stmt = stmt.where(db.or_(*clauses))
        transactions = db.session.scalars(stmt.order_by(Transaction.id.desc()).limit(transaction_limit)).all()
    return can_members, stmt is not None, members, transactions


@bp.get("/search")
@login_required
def search():
    q = request.args.get('q', '').strip()[:120]
    can_members, can_transactions, members, transactions = find_matches(q, 10, 15)
    return render_template('main/search.html', q=q, members=members, transactions=transactions,
                           can_members=can_members, can_transactions=can_transactions)


@bp.get("/search/suggest")
@login_required
def search_suggest():
    """Live suggestions for the top search bar (JSON)."""
    from flask import jsonify, url_for
    q = request.args.get('q', '').strip()[:120]
    _, _, members, transactions = find_matches(q, 5, 6) if len(q) >= 2 else (None, None, [], [])
    return jsonify(
        q=q,
        members=[dict(label=m.full_name, detail=f'{m.student_number} · BS{m.program} {m.year_level}-{m.section}' + ('' if m.active else ' · Inactive'),
                      url=url_for('finance.member_detail', member_id=m.id)) for m in members],
        transactions=[dict(label=f'{t.number} · {t.member_name or t.description}', detail=f'{t.kind} · {t.occurred_on:%d %b %Y}' + (f' · Ref {t.reference}' if t.reference else ''),
                           amount=f'₱{t.amount:,.2f}', status=t.status, url=url_for('finance.transaction_detail', tx_id=t.id)) for t in transactions],
        all_url=url_for('main.search', q=q))


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
