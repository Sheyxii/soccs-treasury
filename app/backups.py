"""Versioned, signed local snapshots. No executable SQL or pickle is accepted."""
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort, send_file, session
from flask_login import current_user, login_required, logout_user
from sqlalchemy import Date, DateTime, Numeric, select
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import User, record_audit, utcnow
from app.finance.forms import ConfirmForm
from app.finance.services import has_authority

bp = Blueprint('backups', __name__)
FORMAT = 1


def directory():
    path = Path(current_app.config.get('BACKUP_DIRECTORY') or Path(current_app.instance_path) / 'backups')
    path.mkdir(parents=True, exist_ok=True)
    return path


def files():
    return sorted(directory().glob('treasury-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)


def signature(payload):
    return hmac.new(current_app.config['SECRET_KEY'].encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_backup(actor='automatic'):
    """Caller holds the standalone application lock; snapshots use one DB transaction."""
    tables = {}
    for table in db.metadata.sorted_tables:
        tables[table.name] = [dict(row) for row in db.session.execute(select(table)).mappings()]
    payload = json.dumps({'format': FORMAT, 'created_at': utcnow().isoformat(), 'tables': tables}, default=str, sort_keys=True, separators=(',', ':'))
    path = directory() / f'treasury-{utcnow():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'payload': payload, 'signature': signature(payload)}), encoding='utf-8')
    temporary.replace(path)
    record_audit('backup.created', actor=actor, record=path.name)
    db.session.commit()
    for old in files()[4:]:
        old.unlink()
    return path


def load_backup(path):
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('Backup exceeds the supported size.')
    envelope = json.loads(path.read_text(encoding='utf-8'))
    payload = envelope['payload']
    if not hmac.compare_digest(envelope['signature'], signature(payload)):
        raise ValueError('Backup integrity check failed. Use an original backup and its original SECRET_KEY.')
    data = json.loads(payload)
    if data['format'] != FORMAT or set(data['tables']) != set(db.metadata.tables):
        raise ValueError('Backup schema does not match this application version.')
    converted = {}
    for table in db.metadata.sorted_tables:
        converted[table.name] = []
        for row in data['tables'][table.name]:
            if set(row) != set(table.columns.keys()):
                raise ValueError('Backup columns do not match this application version.')
            for column in table.columns:
                value = row[column.name]
                if value is None:
                    continue
                if isinstance(column.type, DateTime):
                    row[column.name] = datetime.fromisoformat(value)
                elif isinstance(column.type, Date):
                    row[column.name] = date.fromisoformat(value)
                elif isinstance(column.type, Numeric):
                    row[column.name] = Decimal(str(value))
            converted[table.name].append(row)
    return converted


def restore_backup(path, actor):
    records = load_backup(path)  # Validate before touching the live database.
    create_backup(actor)  # Always keep a recovery snapshot before replacement.
    # DML only: InnoDB and SQLite both roll back all changes on any insert failure.
    try:
        db.session.expunge_all()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        for table in db.metadata.sorted_tables:
            if records[table.name]:
                db.session.execute(table.insert(), records[table.name])
        for user in db.session.scalars(db.select(User)):
            user.revoke_sessions()
        record_audit('backup.restored', actor=actor, record=path.name, remarks='All records restored; officer sessions revoked')
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def automatic_backup():
    if current_app.testing or not current_app.config.get('AUTO_BACKUP', True):
        return
    now = time.monotonic()
    previous = current_app.extensions.get('backup_checked', 0)
    if previous and now - previous < 3600:
        return
    current_app.extensions['backup_checked'] = now
    try:
        existing = files()
        if not existing or time.time() - existing[0].stat().st_mtime >= 7 * 86400:
            create_backup()
            current_app.extensions.pop('backup_error', None)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Automatic backup failed')
        current_app.extensions['backup_error'] = True


def require_backup_authority():
    if not has_authority(current_user, 'backup'):
        abort(403)


def selected_file(name):
    if name not in {p.name for p in files()}:
        abort(404)
    return directory() / name


@bp.route('/backups', methods=['GET', 'POST'])
@login_required
def index():
    require_backup_authority()
    form = ConfirmForm()
    if form.validate_on_submit():
        try:
            create_backup(current_user.username)
            flash('Backup created. The four most recent snapshots are retained.', 'success')
        except OSError:
            db.session.rollback()
            flash('Backup could not be written. Check local disk space and permissions.', 'danger')
        return redirect(url_for('backups.index'))
    return render_template('finance/backups.html', files=files(), form=form)


@bp.get('/backups/<name>/download')
@login_required
def download(name):
    require_backup_authority()
    return send_file(selected_file(name), as_attachment=True)


@bp.post('/backups/<name>/restore')
@login_required
def restore(name):
    require_backup_authority()
    path = selected_file(name)
    if request.form.get('confirmation') != 'RESTORE' or not current_user.check_password(request.form.get('password', '')):
        flash('Enter RESTORE and your current password to confirm replacement of all records.', 'danger')
        return redirect(url_for('backups.index'))
    actor = current_user.username
    try:
        restore_backup(path, actor)
    except (ValueError, KeyError, OSError, TypeError, SQLAlchemyError):
        db.session.rollback()
        flash('Backup could not be restored. Integrity or compatibility checks failed; current records were retained.', 'danger')
        return redirect(url_for('backups.index'))
    logout_user()
    session.clear()
    flash('Backup restored. Sign in with an account from the restored backup.', 'success')
    return redirect(url_for('auth.login'))


@bp.post('/backups/import')
@login_required
def import_backup():
    require_backup_authority()
    upload = request.files.get('backup')
    if not upload:
        abort(400)
    path = directory() / f'import-{secrets.token_hex(8)}.tmp'
    try:
        upload.save(path)
        load_backup(path)
        target = directory() / f'treasury-import-{utcnow():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}.json'
        path.replace(target)
        record_audit('backup.imported', current_user, record=target.name)
        db.session.commit()
        for old in files()[4:]:
            old.unlink()
        flash('Backup imported and verified. Review it below before restoring.', 'success')
    except (ValueError, KeyError, TypeError, OSError):
        flash('This backup is invalid or was signed with another SECRET_KEY.', 'danger')
    finally:
        path.unlink(missing_ok=True)
    return redirect(url_for('backups.index'))
