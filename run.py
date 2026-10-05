"""Local office launcher: python run.py (never enables debug mode)."""
from waitress import serve
from app import create_app

if __name__ == "__main__":
    serve(create_app(), host="127.0.0.1", port=5000)
