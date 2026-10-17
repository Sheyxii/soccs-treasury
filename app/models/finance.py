"""Treasury records. Only posted child records contribute to financial totals."""
from decimal import Decimal
from app.extensions import db
from app.models import utcnow


class AcademicYear(db.Model):
    __tablename__ = 'academic_years'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(9), unique=True, nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    fee = db.Column(db.Numeric(12, 2), nullable=False)
    soccs_percent = db.Column(db.Numeric(5, 2), nullable=False)
    ituh_percent = db.Column(db.Numeric(5, 2), nullable=False)
    css_percent = db.Column(db.Numeric(5, 2), nullable=False)
    __table_args__ = (
        db.CheckConstraint('fee > 0', name='positive_fee'),
        db.CheckConstraint('ends_on >= starts_on', name='year_dates'),
        db.CheckConstraint('soccs_percent >= 0 AND ituh_percent >= 0 AND css_percent >= 0 AND soccs_percent + ituh_percent + css_percent = 100', name='valid_shares'),
    )


class Member(db.Model):
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False, index=True)
    program = db.Column(db.String(2), nullable=False)
    year_level = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(30), nullable=False)
    contact = db.Column(db.String(120), nullable=False, default='')
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.CheckConstraint("program IN ('IT', 'CS')", name='member_program'),
                      db.CheckConstraint('year_level BETWEEN 1 AND 6', name='member_year_level'))


class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(16), nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    categories = db.relationship('BudgetCategory', back_populates='budget', order_by='BudgetCategory.id')
    __table_args__ = (db.CheckConstraint('ends_on >= starts_on', name='budget_dates'),)


class BudgetCategory(db.Model):
    __tablename__ = 'budget_categories'
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budgets.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    allocated = db.Column(db.Numeric(12, 2), nullable=False)
    budget = db.relationship('Budget', back_populates='categories')
    __table_args__ = (db.UniqueConstraint('budget_id', 'name', name='uq_budget_category'),
                      db.CheckConstraint('allocated > 0', name='positive_allocation'))

    @property
    def spent(self):
        return db.session.scalar(db.select(db.func.coalesce(db.func.sum(Expense.amount), 0)).where(Expense.category_id == self.id)) or Decimal('0.00')

    @property
    def remaining(self):
        return self.allocated - self.spent

    @property
    def utilization(self):
        return self.spent / self.allocated * 100 if self.allocated else Decimal(0)


class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(16), nullable=False, default='Pending', index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    occurred_on = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(16), nullable=False, default='Cash')
    reference = db.Column(db.String(80), nullable=False, default='')
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('budget_categories.id'))
    # Nullable unique reservation keys protect pending AND posted payments.
    payment_key = db.Column(db.String(80), unique=True)
    reference_key = db.Column(db.String(80), unique=True)
    submission_key = db.Column(db.String(64), unique=True, nullable=False)
    member_name = db.Column(db.String(120))
    student_number = db.Column(db.String(30))
    program = db.Column(db.String(2))
    soccs_percent = db.Column(db.Numeric(5, 2))
    ituh_percent = db.Column(db.Numeric(5, 2))
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    overspend = db.Column(db.Boolean, nullable=False, default=False)
    remarks = db.Column(db.String(500), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    decided_at = db.Column(db.DateTime)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    verified_at = db.Column(db.DateTime)
    requester = db.relationship('User', foreign_keys=[requester_id])
    approver = db.relationship('User', foreign_keys=[approver_id])
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])
    verifier = db.relationship('User', foreign_keys=[verified_by_id])
    member = db.relationship('Member')
    academic_year = db.relationship('AcademicYear')
    category = db.relationship('BudgetCategory')
    payment = db.relationship('Payment', uselist=False, back_populates='transaction')
    __table_args__ = (
        db.CheckConstraint("kind IN ('Payment', 'Income', 'Expense')", name='transaction_kind'),
        db.CheckConstraint("status IN ('Pending', 'Approved', 'Rejected')", name='transaction_status'),
        db.CheckConstraint('amount > 0', name='positive_transaction_amount'),
    )

    @property
    def number(self):
        return f'TXN-{self.id:06d}'


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), unique=True, nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False)
    transaction = db.relationship('Transaction', back_populates='payment')
    receipt = db.relationship('Receipt', uselist=False, back_populates='payment')
    __table_args__ = (db.UniqueConstraint('member_id', 'academic_year_id', name='uq_member_annual_payment'),)


class Receipt(db.Model):
    __tablename__ = 'receipts'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False, unique=True)
    issued_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    payment = db.relationship('Payment', back_populates='receipt')

    @property
    def number(self):
        return f'RCT-{self.id:06d}'


class Income(db.Model):
    __tablename__ = 'income'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), unique=True, nullable=False)
    source = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    soccs_share = db.Column(db.Numeric(12, 2), nullable=False)
    ituh_share = db.Column(db.Numeric(12, 2), nullable=False)
    css_share = db.Column(db.Numeric(12, 2), nullable=False)
    transaction = db.relationship('Transaction')
    __table_args__ = (db.CheckConstraint('amount = soccs_share + ituh_share + css_share', name='income_shares_balance'),)


class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('budget_categories.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    transaction = db.relationship('Transaction')


class OfficePolicy(db.Model):
    __tablename__ = 'office_policy'
    id = db.Column(db.Integer, primary_key=True)
    overspend_role = db.Column(db.String(32), nullable=True)
    backup_role = db.Column(db.String(32), nullable=True)
