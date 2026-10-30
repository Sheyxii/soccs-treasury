"""Bring the database schema up to date, safely.

  .venv\\Scripts\\python.exe scripts/upgrade_database.py

1. Saves a raw copy of every existing table to instance/pre-upgrade/ (an engineering
   snapshot for recovery, not an importable app backup).
2. Applies any pending migrations (flask db upgrade).
3. Makes sure the five officer roles exist (safe to repeat).
Stop the app before running this.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask_migrate import upgrade  # noqa: E402
from sqlalchemy import MetaData, inspect, select  # noqa: E402
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Role  # noqa: E402
from app.permissions import ROLE_PERMISSIONS  # noqa: E402


def snapshot(app):
    tables = inspect(db.engine).get_table_names()
    if not tables:
        print('Empty database: nothing to snapshot.')
        return
    metadata = MetaData()
    metadata.reflect(bind=db.engine)
    data = {name: [dict(row) for row in db.session.execute(select(metadata.tables[name])).mappings()] for name in tables}
    folder = Path(app.instance_path) / 'pre-upgrade'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'pre-upgrade-{datetime.now():%Y%m%d-%H%M%S}.json'
    path.write_text(json.dumps(data, default=str, indent=1), encoding='utf-8')
    print(f'Saved pre-upgrade snapshot: {path}')


def main():
    try:
        app = create_app()
    except RuntimeError as error:
        sys.exit(str(error))
    with app.app_context():
        try:
            snapshot(app)
        except Exception as error:  # noqa: BLE001 - report and stop before migrating
            sys.exit(f'Cannot read the database ({error}). Is MySQL running and is .env correct?')
        upgrade(directory=str(ROOT / 'migrations'))
        added = [name for name in ROLE_PERMISSIONS if not db.session.scalar(db.select(Role).where(Role.name == name))]
        db.session.add_all(Role(name=name) for name in added)
        db.session.commit()
        print('Schema is up to date.' + (f' Added roles: {", ".join(added)}.' if added else ''))


if __name__ == '__main__':
    main()
