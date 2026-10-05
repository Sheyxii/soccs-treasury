"""Password changes require the current password and confirmation."""
from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired(), Length(max=128)])
    password = PasswordField("New password", validators=[DataRequired(), Length(min=12, max=128)])
    confirm = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Change password")
