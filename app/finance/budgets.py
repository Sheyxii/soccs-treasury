"""Budget plans and auditable category allocations."""
from flask import render_template, redirect, url_for, flash, abort
from flask_login import current_user
from app.extensions import db
from app.models import Budget, BudgetCategory, record_audit
from app.finance import bp
from app.finance.forms import BudgetForm, CategoryForm, ConfirmForm
from app.finance.routes import allow, save


@bp.get('/budgets')
@allow('budgets.manage', 'budgets.view')
def budgets():
    budgets = db.session.scalars(db.select(Budget).order_by(Budget.starts_on.desc())).all()
    return render_template('finance/budgets.html', budgets=budgets)


@bp.route('/budgets/new', methods=['GET', 'POST'])
@allow('budgets.manage')
def budget_form():
    form = BudgetForm()
    if form.validate_on_submit():
        budget = Budget(**{key: getattr(form, key).data for key in ('name', 'kind', 'starts_on', 'ends_on')})
        db.session.add(budget)
        record_audit('budget.created', current_user, record='budget', remarks=budget.name)
        if save():
            return redirect(url_for('finance.budget_detail', budget_id=budget.id))
    return render_template('finance/form.html', form=form, fields=['name', 'kind', 'starts_on', 'ends_on'], title='Create budget', subtitle='Plan a semester or event, then allocate funds by category.', cancel=url_for('finance.budgets'))


@bp.get('/budgets/<int:budget_id>')
@allow('budgets.manage', 'budgets.view')
def budget_detail(budget_id):
    budget = db.get_or_404(Budget, budget_id)
    return render_template('finance/budget.html', budget=budget, form=CategoryForm(), status_form=ConfirmForm())


@bp.post('/budgets/<int:budget_id>/status')
@allow('budgets.manage')
def budget_status(budget_id):
    """Close a finished budget (no new expenses) or reopen it. Records are never removed."""
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    budget = db.get_or_404(Budget, budget_id)
    budget.active = not budget.active
    record_audit('budget.reopened' if budget.active else 'budget.closed', current_user, record=f'budget:{budget.id}', remarks=budget.name)
    if save():
        flash(f'{budget.name} was reopened. New expenses can be recorded against it.' if budget.active
              else f'{budget.name} was closed. It stays in reports, but new expenses cannot be recorded against it.', 'success')
    return redirect(url_for('finance.budget_detail', budget_id=budget.id))


@bp.post('/budgets/<int:budget_id>/categories')
@bp.route('/budgets/<int:budget_id>/categories/<int:category_id>', methods=['GET', 'POST'])
@allow('budgets.manage')
def category_form(budget_id, category_id=None):
    budget = db.get_or_404(Budget, budget_id)
    category = db.get_or_404(BudgetCategory, category_id) if category_id else BudgetCategory(budget=budget)
    if category_id and category.budget_id != budget_id:
        abort(404)
    form = CategoryForm(obj=category if category_id else None)
    if form.validate_on_submit():
        before = category.allocated
        if category_id and form.allocated.data < category.spent:
            flash('Allocation cannot be reduced below posted spending.', 'danger')
        else:
            category.name, category.allocated = form.name.data.strip(), form.allocated.data
            db.session.add(category)
            record_audit('budget.category_updated' if category_id else 'budget.category_created', current_user,
                         record=f'budget:{budget.id}', remarks=f'{category.name}: {before or 0} -> {category.allocated}')
            if save():
                flash('Budget category saved.', 'success')
                return redirect(url_for('finance.budget_detail', budget_id=budget.id))
    return render_template('finance/form.html', form=form, fields=['name', 'allocated'], title='Edit allocation' if category_id else 'Add category', subtitle=budget.name, cancel=url_for('finance.budget_detail', budget_id=budget.id))
