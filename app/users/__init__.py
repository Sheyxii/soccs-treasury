"""Signed-in officer account functionality."""
from flask import Blueprint
bp = Blueprint("users", __name__, url_prefix="/users")
from app.users import routes  # noqa: E402, F401
