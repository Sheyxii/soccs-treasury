"""One-time database setup for XAMPP MySQL/MariaDB.

  .venv\\Scripts\\python.exe scripts/setup_xampp.py [--admin-user root] [--admin-password]

- Creates .env from .env.example if it does not exist, with a new SECRET_KEY and app DB password.
- Uses the local admin account (root) only to create the database and the app account,
  and to grant that account rights on this one database.
- Never changes an existing account's password and never overwrites an existing .env value.
"""
import argparse
import getpass
import re
import secrets
import shutil
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r'^[A-Za-z0-9_]{1,64}$')


def read_env(path):
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values


def fill_env(path, generated):
    """Write generated values only into keys that are blank in .env."""
    lines = path.read_text(encoding='utf-8').splitlines()
    changed = False
    for index, line in enumerate(lines):
        key = line.split('=', 1)[0].strip()
        if key in generated and not line.lstrip().startswith('#') and '=' in line and line.split('=', 1)[1].strip() == '':
            lines[index] = f'{key}={generated[key]}'
            changed = True
    if changed:
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print('Filled in new secrets in .env. Keep a secure copy of SECRET_KEY: backups need it.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--admin-user', default='root')
    parser.add_argument('--admin-password', action='store_true', help='prompt for the admin password (XAMPP root is blank by default)')
    args = parser.parse_args()

    env = ROOT / '.env'
    if not env.exists():
        shutil.copy(ROOT / '.env.example', env)
        print('Created .env from .env.example.')
    fill_env(env, {'SECRET_KEY': secrets.token_hex(32), 'MYSQL_PASSWORD': secrets.token_urlsafe(24)})
    config = read_env(env)
    database, user, password = config.get('MYSQL_DATABASE', 'soccs_treasury_dev'), config.get('MYSQL_USER', 'soccs_app'), config['MYSQL_PASSWORD']
    host, port = config.get('MYSQL_HOST', '127.0.0.1'), int(config.get('MYSQL_PORT', '3306'))
    if not NAME.match(database) or not NAME.match(user):
        sys.exit('MYSQL_DATABASE and MYSQL_USER may only contain letters, numbers and underscores.')

    admin_password = getpass.getpass(f'{args.admin_user} password: ') if args.admin_password else ''
    try:
        connection = pymysql.connect(host=host, port=port, user=args.admin_user, password=admin_password, charset='utf8mb4')
    except pymysql.err.OperationalError as error:
        sys.exit(f'Cannot connect to MySQL at {host}:{port} ({error.args[-1]}).\n'
                 'Start MySQL in the XAMPP Control Panel. If root has a password, add --admin-password.')
    with connection, connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        for account_host in ('localhost', '127.0.0.1'):
            cursor.execute('SELECT 1 FROM mysql.user WHERE User=%s AND Host=%s', (user, account_host))
            if cursor.fetchone():
                print(f"Account '{user}'@'{account_host}' already exists; its password was left unchanged.")
            else:
                cursor.execute('CREATE USER %s@%s IDENTIFIED BY %s', (user, account_host, password))
                print(f"Created account '{user}'@'{account_host}'.")
            cursor.execute(f'GRANT ALL PRIVILEGES ON `{database}`.* TO %s@%s', (user, account_host))
        cursor.execute('FLUSH PRIVILEGES')
    print(f"Database '{database}' is ready. Next: .venv\\Scripts\\python.exe scripts/upgrade_database.py")


if __name__ == '__main__':
    main()
