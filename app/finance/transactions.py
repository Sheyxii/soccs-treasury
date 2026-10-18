"""Transactions, Treasurer decisions, verification and immutable receipts."""
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import Member, AcademicYear, Budget, BudgetCategory, Transaction, Receipt, Income, record_audit, utcnow
from app.finance import bp
from app.finance.forms import TransactionForm, DecisionForm, ConfirmForm
from app.finance.routes import allow, save, paginate
from app.finance.services import (BusinessError, current_year, submit_transaction, decide_transaction,
                                   can_read_transaction, has_authority)


@bp.get('/transactions')
@login_required
def transactions():
    broad = current_user.has_permission('transactions.review') or current_user.has_permission('financial_records.view')
    own = current_user.has_permission('requests.view_own')
    special = has_authority(current_user, 'overspend')
    if not (broad or own or special):
        abort(403)
    stmt = db.select(Transaction)
    if not broad:
        clauses = []
        if own:
            clauses.append(Transaction.requester_id == current_user.id)
        if special:
            clauses.append(Transaction.overspend.is_(True))
        stmt = stmt.where(db.or_(*clauses))
    status, kind = request.args.get('status', ''), request.args.get('kind', '')
    q = request.args.get('q', '').strip()[:120]
    if status in ('Pending', 'Approved', 'Rejected'):
        stmt = stmt.where(Transaction.status == status)
    if kind in ('Payment', 'Income', 'Expense'):
        stmt = stmt.where(Transaction.kind == kind)
    if q:
        clauses = [Transaction.description.contains(q, autoescape=True), Transaction.member_name.contains(q, autoescape=True), Transaction.reference.contains(q, autoescape=True)]
        number = q.upper().removeprefix('TXN-')
        if number.isdigit():
            clauses.append(Transaction.id == int(number))
        stmt = stmt.where(db.or_(*clauses))
    entries = paginate(stmt.order_by(Transaction.created_at.desc(), Transaction.id.desc()))
    return render_template('finance/transactions.html', entries=entries, status=status, kind=kind, q=q)


@bp.route('/transactions/new/<kind>', methods=['GET', 'POST'])
@login_required
def transaction_form(kind):
    permissions = {'Payment': ('payments.record', 'payments.submit'), 'Expense': ('expenses.record', 'expenses.submit'), 'Income': ('income.record',)}
    if kind not in permissions:
        abort(404)
    if not any(current_user.has_permission(p) for p in permissions[kind]):
        abort(403)
    form = TransactionForm()
    members = db.session.scalars(db.select(Member).where(Member.active.is_(True)).order_by(Member.full_name)).all()
    years = db.session.scalars(db.select(AcademicYear).order_by(AcademicYear.starts_on.desc())).all()
    categories = db.session.scalars(db.select(BudgetCategory).join(Budget).where(Budget.active.is_(True)).order_by(Budget.name, BudgetCategory.name)).all()
    form.member_id.choices = [(0, 'Select member')] + [(m.id, f'{m.student_number} · {m.full_name}') for m in members]
    form.academic_year_id.choices = [(0, 'Select academic year')] + [(y.id, f'{y.name} · PHP {y.fee:,.2f}') for y in years]
    form.category_id.choices = [(0, 'Select budget category')] + [(c.id, f'{c.budget.name} / {c.name} · PHP {c.remaining:,.2f} remaining') for c in categories]
    if request.method == 'GET':
        if kind == 'Payment':
            year = current_year() or (years[0] if years else None)
            form.member_id.data = request.args.get('member', 0, type=int)
            if year:
                form.academic_year_id.data, form.amount.data = year.id, year.fee
            form.description.data = 'Annual membership fee'
        elif kind == 'Income':
            form.description.data = 'Water refilling station collection'
    if form.validate_on_submit():
        try:
            tx = submit_transaction(current_user, kind=kind, **{name: getattr(form, name).data for name in ('amount', 'occurred_on', 'description', 'method', 'reference', 'submission_key', 'member_id', 'academic_year_id', 'category_id')})
            if save():
                flash('Transaction posted.' if tx.status == 'Approved' else 'Request saved as Pending. Approval is required before it affects the accounts.', 'success' if tx.status == 'Approved' else 'warning')
                return redirect(url_for('finance.transaction_detail', tx_id=tx.id))
        except BusinessError as error:
            db.session.rollback()
            flash(str(error), 'danger')
        except IntegrityError:
            db.session.rollback()
            flash('A payment, GCash reference, or form submission already exists. Review the transaction list.', 'danger')
    fields = (['member_id', 'academic_year_id'] if kind == 'Payment' else ['category_id'] if kind == 'Expense' else []) + ['amount', 'occurred_on', 'method', 'reference', 'description']
    return render_template('finance/transaction_form.html', form=form, fields=fields, kind=kind, years=years, categories=categories)


@bp.get('/transactions/<int:tx_id>')
@login_required
def transaction_detail(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    if not can_read_transaction(current_user, tx):
        abort(403)
    income = db.session.scalar(db.select(Income).where(Income.transaction_id == tx.id))
    return render_template('finance/transaction.html', tx=tx, income=income, form=DecisionForm(), verify_form=ConfirmForm())


@bp.post('/transactions/<int:tx_id>/decide')
@login_required
def transaction_decide(tx_id):
    form = DecisionForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        tx = decide_transaction(tx_id, current_user, form.decision.data, form.remarks.data or '')
        if save():
            flash('Decision saved.' if tx.status != 'Pending' else 'Over-budget expense held for authorized approval. Enter a reason and approve explicitly.', 'success' if tx.status != 'Pending' else 'warning')
    except BusinessError as error:
        db.session.rollback()
        flash(str(error), 'danger')
    except IntegrityError:
        db.session.rollback()
        flash('This transaction conflicts with an existing record; nothing was posted.', 'danger')
    return redirect(url_for('finance.transaction_detail', tx_id=tx_id))


@bp.post('/transactions/<int:tx_id>/verify')
@allow('payments.verify')
def transaction_verify(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    if tx.kind != 'Payment' or tx.status != 'Approved':
        abort(400)
    if not tx.verified_at:
        tx.verified_by_id, tx.verified_at = current_user.id, utcnow()
        record_audit('payment.verified', current_user, record=tx.number, remarks='Manually verified payment evidence')
        save()
    flash('Payment verification recorded.', 'success')
    return redirect(url_for('finance.transaction_detail', tx_id=tx_id))


@bp.get('/receipts/<int:receipt_id>')
@login_required
def receipt(receipt_id):
    receipt = db.get_or_404(Receipt, receipt_id)
    tx = receipt.payment.transaction
    if not can_read_transaction(current_user, tx):
        abort(403)
    return render_template('finance/receipt.html', receipt=receipt, tx=tx)
