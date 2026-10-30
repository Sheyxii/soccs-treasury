"""Member directory, annual payment status and profile history."""
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from app.extensions import db
from app.models import Member, Payment, Transaction, AcademicYear, record_audit
from app.finance import bp
from app.finance.forms import MemberForm, ConfirmForm
from app.finance.routes import allow, save, paginate
from app.finance.services import current_year


@bp.get('/members')
@allow('members.manage', 'payments.verify')
def members():
    years = db.session.scalars(db.select(AcademicYear).order_by(AcademicYear.starts_on.desc())).all()
    year_id = request.args.get('year', type=int)
    year = db.session.get(AcademicYear, year_id) if year_id else current_year()
    year = year or (years[0] if years else None)
    paid = db.select(Payment.member_id).where(Payment.academic_year_id == year.id) if year else db.select(Payment.member_id).where(db.false())
    stmt = db.select(Member)
    q = request.args.get('q', '').strip()[:120]
    if q:
        stmt = stmt.where(db.or_(Member.full_name.contains(q, autoescape=True), Member.student_number.contains(q, autoescape=True), Member.section.contains(q, autoescape=True)))
    program = request.args.get('program', '')
    if program in ('IT', 'CS'):
        stmt = stmt.where(Member.program == program)
    status = request.args.get('status', '')
    if status == 'paid':
        stmt = stmt.where(Member.id.in_(paid))
    if status == 'unpaid':  # only active members can still owe the annual fee
        stmt = stmt.where(Member.active.is_(True), Member.id.not_in(paid))
    if status == 'inactive':
        stmt = stmt.where(Member.active.is_(False))
    entries = paginate(stmt.order_by(Member.full_name))
    paid_ids = set(db.session.scalars(paid))
    pending_ids = set(db.session.scalars(db.select(Transaction.member_id).where(Transaction.academic_year_id == (year.id if year else -1), Transaction.status == 'Pending', Transaction.kind == 'Payment')))
    inactive_ids = [m.id for m in entries.items if not m.active]
    with_records = set(db.session.scalars(db.select(Transaction.member_id).where(Transaction.member_id.in_(inactive_ids)))) if inactive_ids else set()
    deletable_ids = set(inactive_ids) - with_records
    return render_template('finance/members.html', entries=entries, year=year, years=years, paid_ids=paid_ids, pending_ids=pending_ids, q=q, program=program, status=status,
                           deletable_ids=deletable_ids, delete_form=ConfirmForm())


@bp.route('/members/new', methods=['GET', 'POST'])
@bp.route('/members/<int:member_id>/edit', methods=['GET', 'POST'])
@allow('members.manage')
def member_form(member_id=None):
    member = db.get_or_404(Member, member_id) if member_id else Member()
    form = MemberForm(obj=member if member_id else None)
    if form.validate_on_submit():
        for name in ('student_number', 'full_name', 'program', 'year_level', 'section', 'contact', 'active'):
            value = getattr(form, name).data
            setattr(member, name, value.strip() if isinstance(value, str) else value)
        if not member.full_name or not member.section:
            flash('Full name and section cannot be blank.', 'danger')
        else:
            db.session.add(member)
            record_audit('member.updated' if member_id else 'member.created', current_user, record=f'member:{member.student_number}')
            if save():
                flash('Member record saved.', 'success')
                return redirect(url_for('finance.member_detail', member_id=member.id))
    return render_template('finance/form.html', form=form, fields=['student_number', 'full_name', 'program', 'year_level', 'section', 'contact', 'active'], title='Edit member' if member_id else 'Add member', subtitle='Student information is kept separate from officer accounts.', cancel=url_for('finance.members'))


def has_records(member_id):
    """Any payment request (pending, approved or rejected) keeps a member from being deleted."""
    return db.session.scalar(db.select(Transaction.id).where(Transaction.member_id == member_id).limit(1)) is not None


@bp.get('/members/<int:member_id>')
@allow('members.manage', 'payments.verify')
def member_detail(member_id):
    member = db.get_or_404(Member, member_id)
    stmt = db.select(Transaction).where(Transaction.member_id == member_id)
    if current_user.role.name == 'Coordinator':
        stmt = stmt.where(db.or_(Transaction.requester_id == current_user.id, Transaction.status == 'Approved'))
    transactions = db.session.scalars(stmt.order_by(Transaction.id.desc())).all()
    return render_template('finance/member.html', member=member, transactions=transactions,
                           can_delete=not member.active and not has_records(member.id), delete_form=ConfirmForm())


@bp.post('/members/<int:member_id>/delete')
@allow('members.manage')
def member_delete(member_id):
    """Permanently remove an inactive member who has no payment records."""
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    member = db.get_or_404(Member, member_id)
    if member.active:
        flash('Mark the member as inactive before deleting them.', 'danger')
        return redirect(url_for('finance.member_detail', member_id=member.id))
    if has_records(member.id):
        flash('This member has payment records, so they cannot be deleted. They stay inactive to keep the financial history intact.', 'danger')
        return redirect(url_for('finance.member_detail', member_id=member.id))
    label = f'member:{member.student_number}'
    name = member.full_name
    db.session.delete(member)
    record_audit('member.deleted', current_user, record=label, remarks=name[:255])
    if save():
        flash(f'{name} was deleted.', 'success')
        return redirect(url_for('finance.members', status='inactive'))
    return redirect(url_for('finance.member_detail', member_id=member_id))
