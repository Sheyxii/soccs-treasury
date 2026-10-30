"""Production launcher: python run.py (never enables debug mode).

HOST, PORT and THREADS come from .env. The defaults serve only this computer (127.0.0.1:5000).
Run one process only: backups and posting are serialized inside this process.
"""
import logging
import os
import sys
from waitress import serve
from app import create_app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        app = create_app()
    except RuntimeError as error:
        sys.exit(f"Cannot start SOCCS Treasury: {error}")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    threads = int(os.environ.get("THREADS", "8"))
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print(f"SOCCS Treasury is running at http://{shown}:{port}  (press Ctrl+C to stop)", flush=True)
    # Behind a reverse proxy, set TRUST_PROXY=1 in .env; the app (ProxyFix) then reads X-Forwarded-* headers.
    serve(app, host=host, port=port, threads=threads, ident="SOCCS Treasury")
