"""Confirmed annual fee policies; used policies are immutable."""
from flask import render_template, redirect, url_for, flash
from flask_login import current_user
from app.extensions import db
from app.models import AcademicYear, Transaction, OfficePolicy, record_audit
from app.finance import bp
from app.finance.forms import YearForm
from app.finance.routes import allow, save


@bp.route('/settings', methods=['GET', 'POST'])
@allow('budgets.manage')
def settings():
    form = YearForm()
    if form.validate_on_submit():
        if form.soccs_percent.data + form.ituh_percent.data + form.css_percent.data != 100:
            flash('SOCCS, ITUH and CSS percentages must total 100%.', 'danger')
        elif int(form.name.data[5:]) != int(form.name.data[:4]) + 1:
            flash('Academic year must contain consecutive years.', 'danger')
        elif db.session.scalar(db.select(AcademicYear.id).where(AcademicYear.starts_on <= form.ends_on.data, AcademicYear.ends_on >= form.starts_on.data)):
            flash('Academic year dates overlap an existing year.', 'danger')
        else:
            year = AcademicYear(**{key: getattr(form, key).data for key in ('name', 'starts_on', 'ends_on', 'fee', 'soccs_percent', 'ituh_percent', 'css_percent')})
            db.session.add(year)
            record_audit('academic_year.created', current_user, record=year.name, remarks=f'Fee {year.fee}; SOCCS {year.soccs_percent}%, ITUH {year.ituh_percent}%, CSS {year.css_percent}%')
            if save():
                flash('Academic year and fee policy saved.', 'success')
                return redirect(url_for('finance.settings'))
    years = db.session.scalars(db.select(AcademicYear).order_by(AcademicYear.starts_on.desc())).all()
    return render_template('finance/settings.html', form=form, years=years, policy=db.session.get(OfficePolicy, 1))
