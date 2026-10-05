"""Self-service account access never accepts role or active-status changes."""
from flask import flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, logout_user
from app.extensions import db
from app.models import record_audit
from app.users import bp
from app.users.forms import ChangePasswordForm

@bp.route("/me", methods=["GET", "POST"])
@login_required
def profile():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Current password is incorrect.")
        else:
            current_user.set_password(form.password.data)
            record_audit("password.changed", current_user, record=f"user:{current_user.id}")
            db.session.commit()
            logout_user()
            session.clear()
            flash("Password changed. Please sign in again.", "success")
            return redirect(url_for("auth.login"))
    return render_template("users/profile.html", form=form)
