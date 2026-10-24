"""Save a local pre-upgrade data snapshot, then apply versioned migrations."""
import json
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import MetaData, select
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.extensions import db
from flask_migrate import upgrade


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        if metadata.tables:
            snapshot = {}
            with db.engine.connect() as connection:
                for table in metadata.sorted_tables:
                    snapshot[table.name] = [dict(row) for row in connection.execute(select(table)).mappings()]
            folder = Path(app.instance_path) / 'pre-upgrade'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f'pre-upgrade-{datetime.now():%Y%m%d-%H%M%S}.json'
            path.write_text(json.dumps(snapshot, default=str), encoding='utf-8')
            print('Pre-upgrade data snapshot saved under instance/pre-upgrade.')
        upgrade()
        print('Database migrations applied.')
