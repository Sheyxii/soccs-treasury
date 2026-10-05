"""Officer identities are separate from future student/member records."""
import re
import secrets
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.permissions import ROLE_PERMISSIONS

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def normalize_username(value):
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", value):
        raise ValueError("Username must be 3-80 letters, numbers, dots, underscores or hyphens, starting with a letter or number.")
    return value

def validate_password(value):
    if not 12 <= len(value) <= 128 or not value.strip():
        raise ValueError("Password must contain 12-128 characters and cannot be only spaces.")

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    __table_args__ = (db.CheckConstraint("name IN ('Coordinator', 'Treasurer', 'Auditor', 'President', 'Adviser')", name="valid_role_name"),)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    role = db.relationship("Role")
    active = db.Column(db.Boolean, nullable=False, default=True)
    session_token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    @property
    def is_active(self):
        return self.active

    def get_id(self):
        return self.session_token

    def revoke_sessions(self):
        self.session_token = secrets.token_hex(32)

    def set_password(self, value):
        validate_password(value)
        self.password_hash = generate_password_hash(value)
        self.revoke_sessions()

    def check_password(self, value):
        return check_password_hash(self.password_hash, value)

    def has_permission(self, permission):
        return self.active and self.role is not None and permission in ROLE_PERMISSIONS.get(self.role.name, ())

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor = db.Column(db.String(160), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    record = db.Column(db.String(120), nullable=False)
    remarks = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

def record_audit(action, user=None, *, actor=None, record="session", remarks=""):
    """Stage an event in the same transaction as its change. Never log secrets."""
    db.session.add(AuditLog(user_id=user.id if user else None,
                           actor=actor or (user.username if user else "anonymous"),
                           action=action, record=record, remarks=remarks))
