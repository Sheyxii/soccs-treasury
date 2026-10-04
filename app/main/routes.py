"""The first route: a public development landing page with no private data."""

from flask import render_template

from app.main import bp


@bp.get("/")
def index():
    return render_template("main/index.html")
