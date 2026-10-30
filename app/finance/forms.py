"""Server-side validation for all treasury forms."""
import secrets
from decimal import Decimal, InvalidOperation
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, TextAreaField, BooleanField, HiddenField, SubmitField
from wtforms.validators import InputRequired, Length, NumberRange, Optional, Regexp, ValidationError, StopValidation
from app.finance.services import today


def cents(form, field):
    try:
        invalid = field.data is not None and (not field.data.is_finite() or field.data != field.data.quantize(Decimal('.01')))
    except InvalidOperation:
        invalid = True
    if invalid:
        raise StopValidation('Use a finite amount with at most two decimal places.')


AMOUNT = [InputRequired(), cents, NumberRange(min=Decimal('.01'), max=Decimal('9999999999.99'))]


class MemberForm(FlaskForm):
    student_number = StringField('Student number', filters=[lambda value: value.strip() if isinstance(value, str) else value],
                                 validators=[InputRequired(), Regexp(r'^\d{4}-\d{4}\Z', message='Use the format 1234-5678: four digits, a hyphen, then four digits.')],
                                 render_kw={'inputmode': 'numeric', 'pattern': r'\d{4}-\d{4}', 'maxlength': 9, 'placeholder': '2026-0001',
                                            'title': 'Four digits, a hyphen, then four digits (e.g. 2026-0001)', 'data-student-number': ''})
    full_name = StringField('Full name', validators=[InputRequired(), Length(min=2, max=120)])
    program = SelectField('Program', choices=[('IT', 'BS Information Technology'), ('CS', 'BS Computer Science')])
    year_level = SelectField('Year level', coerce=int, choices=[(x, f'Year {x}') for x in range(1, 7)])
    section = StringField('Section', validators=[InputRequired(), Length(max=30)])
    contact = StringField('Contact information (optional)', validators=[Optional(), Length(max=120)])
    active = BooleanField('Active member', default=True)
    submit = SubmitField('Save member')


class TransactionForm(FlaskForm):
    submission_key = HiddenField(default=lambda: secrets.token_hex(24), validators=[InputRequired(), Length(min=48, max=48)])
    member_id = SelectField('Member', coerce=int, choices=[], validators=[Optional()])
    academic_year_id = SelectField('Academic year', coerce=int, choices=[], validators=[Optional()])
    category_id = SelectField('Budget category', coerce=int, choices=[], validators=[Optional()])
    amount = DecimalField('Amount (PHP)', places=None, validators=AMOUNT)
    occurred_on = DateField('Transaction date', default=today, validators=[InputRequired()])
    method = SelectField('Payment method', choices=[('Cash', 'Cash'), ('GCash', 'GCash')])
    reference = StringField('Receipt / reference number', validators=[Optional(), Length(max=80)])
    description = TextAreaField('Description / purpose', validators=[InputRequired(), Length(min=3, max=500)])
    submit = SubmitField('Save transaction')


class DecisionForm(FlaskForm):
    remarks = TextAreaField('Decision remarks', validators=[Optional(), Length(max=500)])
    decision = SelectField('Decision', choices=[('approve', 'Approve'), ('reject', 'Reject')])
    submit = SubmitField('Confirm decision')


class BudgetForm(FlaskForm):
    name = StringField('Budget name', validators=[InputRequired(), Length(min=3, max=120)])
    kind = SelectField('Budget type', choices=[('Semester', 'Semester'), ('Event', 'Event')])
    starts_on = DateField('Start date', validators=[InputRequired()])
    ends_on = DateField('End date', validators=[InputRequired()])
    submit = SubmitField('Create budget')

    def validate_ends_on(self, field):
        if self.starts_on.data and field.data < self.starts_on.data:
            raise ValidationError('End date must be on or after the start date.')


class CategoryForm(FlaskForm):
    name = StringField('Category name', validators=[InputRequired(), Length(min=2, max=80)])
    allocated = DecimalField('Allocation (PHP)', places=None, validators=AMOUNT)
    submit = SubmitField('Save category')


class YearForm(BudgetForm):
    name = StringField('Academic year', validators=[InputRequired(), Regexp(r'^20\d{2}-20\d{2}$', message='Use YYYY-YYYY, for example 2026-2027.')])
    kind = None
    fee = DecimalField('Annual membership fee (PHP)', default=250, places=None, validators=AMOUNT)
    soccs_percent = DecimalField('SOCCS share (%)', default=40, places=None, validators=[InputRequired(), cents, NumberRange(0, 100)])
    ituh_percent = DecimalField('ITUH share (%)', default=30, places=None, validators=[InputRequired(), cents, NumberRange(0, 100)])
    css_percent = DecimalField('CSS share (%)', default=30, places=None, validators=[InputRequired(), cents, NumberRange(0, 100)])
    submit = SubmitField('Save academic year')


class ConfirmForm(FlaskForm):
    submit = SubmitField('Confirm')
