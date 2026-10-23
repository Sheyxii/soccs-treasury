"""Cash-basis reports built only from posted ledger entries."""
import csv
import io
from datetime import date
from decimal import Decimal
from flask import render_template, request, Response, abort
from flask_login import current_user
from app.extensions import db
from app.models import Member, AcademicYear, Payment, Budget, BudgetCategory, Transaction, Income, Expense
from app.finance import bp
from app.finance.routes import allow
from app.finance.services import today, totals, current_year


def dashboard_data():
    data = totals()
    year = current_year()
    data['members'] = db.session.scalar(db.select(db.func.count(Member.id)).where(Member.active.is_(True)))
    data['paid'] = db.session.scalar(db.select(db.func.count(Payment.id)).join(Member).where(Member.active.is_(True), Payment.academic_year_id == (year.id if year else -1)))
    data['year'] = year
    data['pending'] = db.session.scalar(db.select(db.func.count(Transaction.id)).where(Transaction.status == 'Pending'))
    data['allocated'] = db.session.scalar(db.select(db.func.coalesce(db.func.sum(BudgetCategory.allocated), 0))) or Decimal(0)
    data['utilization'] = data['expenses'] / data['allocated'] * 100 if data['allocated'] else 0
    data['categories'] = db.session.scalars(db.select(BudgetCategory).join(Budget).where(Budget.active.is_(True)).order_by(Budget.starts_on.desc()).limit(5)).all()
    can_read_records = current_user.has_permission('transactions.review') or current_user.has_permission('financial_records.view')
    data['recent'] = db.session.scalars(db.select(Transaction).order_by(Transaction.id.desc()).limit(6)).all() if can_read_records else []
    rows = db.session.execute(db.select(Transaction.occurred_on, Transaction.kind, Transaction.amount).where(Transaction.status == 'Approved', Transaction.occurred_on >= today().replace(day=1))).all()
    data['month_income'] = sum((r.amount for r in rows if r.kind != 'Expense'), Decimal(0))
    data['month_expenses'] = sum((r.amount for r in rows if r.kind == 'Expense'), Decimal(0))
    chart = []
    for offset in range(5, -1, -1):
        index = today().year * 12 + today().month - 1 - offset
        start = date(index // 12, index % 12 + 1, 1)
        next_index = index + 1
        next_start = date(next_index // 12, next_index % 12 + 1, 1)
        from datetime import timedelta
        t = totals(start, next_start - timedelta(days=1))
        chart.append(dict(label=start.strftime('%b'), income=t['soccs'], expense=t['expenses']))
    maximum = max([max(row['income'], row['expense']) for row in chart] + [Decimal(1)])
    for row in chart:
        row['income_height'] = float(row['income'] / maximum * 100)
        row['expense_height'] = float(row['expense'] / maximum * 100)
    data['chart'] = chart
    return data


def report_data():
    try:
        start = date.fromisoformat(request.args.get('start') or today().replace(day=1).isoformat())
        end = date.fromisoformat(request.args.get('end') or today().isoformat())
    except ValueError:
        abort(400, 'Use valid start and end dates.')
    if end < start:
        abort(400, 'End date must follow the start date.')
    budget_id = request.args.get('budget', type=int)
    budget = db.get_or_404(Budget, budget_id) if budget_id else None
    income = db.select(Income).join(Transaction).where(Transaction.occurred_on.between(start, end))
    expense = db.select(Expense).join(Transaction).where(Transaction.occurred_on.between(start, end))
    if budget:
        expense = expense.join(BudgetCategory).where(BudgetCategory.budget_id == budget.id)
    incomes = db.session.scalars(income.order_by(Transaction.occurred_on, Transaction.id)).all()
    expenses = db.session.scalars(expense.order_by(Transaction.occurred_on, Transaction.id)).all()
    values = totals(start, end)
    values['expenses'] = sum((e.amount for e in expenses), Decimal(0))
    values['balance'] = values['soccs'] - values['expenses']
    categories = db.session.scalars(db.select(BudgetCategory).where(BudgetCategory.budget_id == budget.id) if budget else db.select(BudgetCategory)).all()
    spending = {c.id: sum((e.amount for e in expenses if e.category_id == c.id), Decimal(0)) for c in categories}
    year_id = request.args.get('year', type=int)
    year = db.get_or_404(AcademicYear, year_id) if year_id else current_year()
    count = db.session.scalar(db.select(db.func.count(Member.id)).where(Member.active.is_(True)))
    paid = db.session.scalar(db.select(db.func.count(Payment.id)).join(Member).where(Member.active.is_(True), Payment.academic_year_id == (year.id if year else -1)))
    return dict(start=start, end=end, budget=budget, values=values, incomes=incomes, expenses=expenses, categories=categories, spending=spending,
                year=year, member_count=count, paid_count=paid, budgets=db.session.scalars(db.select(Budget).order_by(Budget.starts_on.desc())).all(),
                years=db.session.scalars(db.select(AcademicYear).order_by(AcademicYear.starts_on.desc())).all())


@bp.get('/reports')
@allow('reports.view')
def reports():
    return render_template('finance/reports.html', **report_data())


def csv_safe(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text


@bp.get('/reports/export')
@allow('reports.view')
def report_export():
    data = report_data()
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['SOCCS Treasury financial report', data['start'], data['end']])
    writer.writerow(['Scope', 'Organization income; selected budget expenses only' if data['budget'] else 'All organization activity'])
    writer.writerow(['Category spending scope', csv_safe(data['budget'].name) if data['budget'] else 'All budgets'])
    for key in ('gross', 'soccs', 'ituh', 'css', 'expenses'):
        writer.writerow([key, f"{data['values'][key]:.2f}"])
    if not data['budget']:
        writer.writerow(['Net SOCCS movement', f"{data['values']['balance']:.2f}"])
    writer.writerow([])
    writer.writerow(['Transaction', 'Date', 'Type', 'Description', 'Gross amount', 'SOCCS', 'ITUH', 'CSS'])
    for inc in data['incomes']:
        tx = inc.transaction
        writer.writerow([tx.number, tx.occurred_on, inc.source, csv_safe(tx.description), inc.amount, inc.soccs_share, inc.ituh_share, inc.css_share])
    for exp in data['expenses']:
        tx = exp.transaction
        writer.writerow([tx.number, tx.occurred_on, 'Expense', csv_safe(tx.description), exp.amount, '', '', ''])
    writer.writerow([])
    writer.writerow(['Budget', 'Category', 'Allocation', 'Period spending', 'Lifetime spending', 'Remaining'])
    for category in data['categories']:
        writer.writerow([csv_safe(category.budget.name), csv_safe(category.name), category.allocated, data['spending'][category.id], category.spent, category.remaining])
    writer.writerow([])
    writer.writerow(['Membership academic year', data['year'].name if data['year'] else 'Not configured'])
    writer.writerow(['Active members', data['member_count'], 'Paid', data['paid_count'], 'Unpaid', data['member_count']-data['paid_count']])
    return Response('\ufeff' + out.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=soccs-financial-report.csv'})
