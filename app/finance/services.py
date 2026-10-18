"""Atomic posting and review. Callers commit once, with the audit records."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from flask import abort
from app.extensions import db
from app.models import (AcademicYear, Member, BudgetCategory, Transaction, Payment,
                        Receipt, Income, Expense, OfficePolicy, record_audit, utcnow)


class BusinessError(ValueError):
    pass


def today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def money(value):
    value = Decimal(str(value))
    if not value.is_finite() or value <= 0 or value > Decimal('9999999999.99') or value != value.quantize(Decimal('.01')):
        raise BusinessError('Amount must be positive, with at most two decimal places.')
    return value


def policy():
    return db.session.get(OfficePolicy, 1)


def has_authority(user, kind):
    settings = policy()
    return bool(settings and user.is_authenticated and user.active and
                getattr(settings, kind + '_role', None) == user.role.name)


def can_read_transaction(user, transaction):
    if user.has_permission('transactions.review') or user.has_permission('financial_records.view'):
        return True
    if user.has_permission('requests.view_own') and transaction.requester_id == user.id:
        return True
    return has_authority(user, 'overspend') and transaction.overspend


def current_year():
    return db.session.scalar(db.select(AcademicYear).where(AcademicYear.starts_on <= today(), AcademicYear.ends_on >= today()).order_by(AcademicYear.starts_on.desc()))


def post_transaction(tx, actor, remarks=''):
    """Create all official records together. Never call for a rejected/posted item."""
    if tx.status != 'Pending':
        raise BusinessError('This transaction has already been decided.')
    if tx.kind == 'Payment':
        share = (tx.amount * tx.soccs_percent / Decimal(100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        ituh = (tx.amount * tx.ituh_percent / Decimal(100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        payment = Payment(transaction=tx, member_id=tx.member_id, academic_year_id=tx.academic_year_id)
        db.session.add(payment)
        db.session.add(Receipt(payment=payment))
        db.session.add(Income(transaction=tx, source='Membership fees', amount=tx.amount,
                              soccs_share=share, ituh_share=ituh, css_share=tx.amount-share-ituh))
    elif tx.kind == 'Income':
        db.session.add(Income(transaction=tx, source='Water refilling station', amount=tx.amount,
                              soccs_share=tx.amount, ituh_share=Decimal(0), css_share=Decimal(0)))
    else:
        db.session.add(Expense(transaction=tx, category_id=tx.category_id, amount=tx.amount))
    tx.status = 'Approved'
    tx.approver_id = actor.id
    tx.decided_at = utcnow()
    tx.remarks = remarks
    record_audit('transaction.approved', actor, record=tx.number, remarks=remarks[:255])
    db.session.flush()


def submit_transaction(actor, *, kind, amount, occurred_on, description, method, reference,
                       submission_key, member_id=None, academic_year_id=None, category_id=None):
    permission = {'Payment': ('payments.record', 'payments.submit'), 'Expense': ('expenses.record', 'expenses.submit'), 'Income': ('income.record',)}
    if kind not in permission or not any(actor.has_permission(p) for p in permission[kind]):
        abort(403)
    if db.session.scalar(db.select(Transaction.id).where(Transaction.submission_key == submission_key)):
        raise BusinessError('This form was already submitted. Open the transaction list to review it.')
    amount = money(amount)
    description = description.strip()
    if not 3 <= len(description) <= 500:
        raise BusinessError('Description must contain 3–500 characters.')
    if not isinstance(occurred_on, date) or occurred_on > today():
        raise BusinessError('Transaction date cannot be in the future.')
    if method not in ('Cash', 'GCash'):
        raise BusinessError('Select Cash or GCash.')
    reference = reference.strip()
    if method == 'GCash' and (not reference.isdigit() or not 10 <= len(reference) <= 20):
        raise BusinessError('GCash reference must contain 10–20 digits; verify it against the payment record.')
    if kind == 'Expense' and not reference:
        raise BusinessError('A receipt or expense reference is required.')
    tx = Transaction(kind=kind, amount=amount, occurred_on=occurred_on, description=description,
                     method=method, reference=reference, requester_id=actor.id, submission_key=submission_key, status='Pending')
    if method == 'GCash' and kind in ('Payment', 'Income'):
        tx.reference_key = reference
    if kind == 'Payment':
        member = db.session.get(Member, member_id)
        year = db.session.get(AcademicYear, academic_year_id)
        if not member or not member.active or not year:
            raise BusinessError('Select an active member and a configured academic year.')
        if not year.starts_on <= occurred_on <= year.ends_on:
            raise BusinessError('Payment date must fall within the selected academic year.')
        if amount != year.fee:
            raise BusinessError(f'The annual membership fee is PHP {year.fee:,.2f}. Partial payments are not supported.')
        tx.member_id, tx.academic_year_id = member.id, year.id
        tx.member_name, tx.student_number, tx.program = member.full_name, member.student_number, member.program
        tx.soccs_percent, tx.ituh_percent = year.soccs_percent, year.ituh_percent
        tx.payment_key = f'{member.id}:{year.id}'
        if db.session.scalar(db.select(Transaction.id).where(Transaction.payment_key == tx.payment_key)):
            raise BusinessError('This member already has an approved payment or pending request for this academic year.')
    if kind == 'Expense':
        category = db.session.scalar(db.select(BudgetCategory).where(BudgetCategory.id == category_id).with_for_update())
        if not category or not category.budget.active:
            raise BusinessError('Select a category from an active budget.')
        if not category.budget.starts_on <= occurred_on <= category.budget.ends_on:
            raise BusinessError('Expense date must fall within the selected budget period.')
        tx.category_id = category.id
        tx.overspend = amount > category.remaining
    db.session.add(tx)
    db.session.flush()
    record_audit('transaction.submitted', actor, record=tx.number, remarks=f'{kind}: {amount:.2f}')
    if actor.role.name == 'Treasurer' and not tx.overspend:
        post_transaction(tx, actor, 'Recorded by Treasurer')
    return tx


def decide_transaction(tx_id, actor, decision, remarks):
    tx = db.session.scalar(db.select(Transaction).where(Transaction.id == tx_id).with_for_update())
    if not tx:
        abort(404)
    treasurer = actor.has_permission('transactions.review')
    authorized = has_authority(actor, 'overspend') and tx.overspend
    if not (treasurer or authorized):
        abort(403)
    if tx.status != 'Pending':
        raise BusinessError('This transaction has already been decided. Posted records cannot be edited.')
    if decision not in ('approve', 'reject'):
        raise BusinessError('Choose approve or reject.')
    if decision == 'reject':
        if not remarks.strip():
            raise BusinessError('A rejection reason is required.')
        tx.status, tx.remarks = 'Rejected', remarks
        tx.approver_id, tx.decided_at = actor.id, utcnow()
        tx.payment_key = tx.reference_key = None
        record_audit('transaction.rejected', actor, record=tx.number, remarks=remarks[:255])
        return tx
    if tx.kind == 'Expense':
        category = db.session.scalar(db.select(BudgetCategory).where(BudgetCategory.id == tx.category_id).with_for_update())
        tx.overspend = tx.overspend or tx.amount > category.remaining
        if tx.overspend:
            # A Coordinator request still needs Treasurer review before special authorization.
            if tx.requester.role.name == 'Coordinator' and tx.reviewer_id is None:
                if not treasurer:
                    raise BusinessError('The Treasurer must review this Coordinator request first.')
                tx.reviewer_id, tx.reviewed_at = actor.id, utcnow()
                record_audit('transaction.reviewed', actor, record=tx.number, remarks='Forwarded for overspending approval')
            if not has_authority(actor, 'overspend'):
                # Keep the newly discovered warning/review rather than posting any expense.
                record_audit('expense.held', actor, record=tx.number, remarks='Over budget; authorized approval required')
                return tx
            if not remarks.strip():
                raise BusinessError('Explain why this over-budget expense is authorized.')
    post_transaction(tx, actor, remarks)
    return tx


def totals(start=None, end=None):
    def query(model, column):
        stmt = db.select(db.func.coalesce(db.func.sum(column), 0)).select_from(model).join(Transaction)
        if start:
            stmt = stmt.where(Transaction.occurred_on >= start)
        if end:
            stmt = stmt.where(Transaction.occurred_on <= end)
        return db.session.scalar(stmt) or Decimal('0.00')
    gross = query(Income, Income.amount)
    soccs = query(Income, Income.soccs_share)
    expenses = query(Expense, Expense.amount)
    return dict(gross=gross, soccs=soccs, sub=gross-soccs, ituh=query(Income, Income.ituh_share), css=query(Income, Income.css_share), expenses=expenses, balance=soccs-expenses)
