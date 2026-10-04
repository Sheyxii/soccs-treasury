"""Create and configure the SOCCS Treasury application."""

from flask import Flask

from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from app.main import bp

    app.register_blueprint(bp)
    return app
