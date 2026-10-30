"""Run the full test suite against a throw-away MySQL/MariaDB database.

  .venv\\Scripts\\python.exe scripts/test_mysql.py [--admin-user root] [--admin-password] [pytest args]

Creates a random soccs_treasury_test_* database with the local admin account, runs pytest
against it, and then drops only that generated database. Operational data is never touched.
"""
import argparse
import getpass
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pymysql

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=3306)
    parser.add_argument('--admin-user', default='root')
    parser.add_argument('--admin-password', action='store_true', help='prompt for the admin password')
    args, pytest_args = parser.parse_known_args()
    password = getpass.getpass(f'{args.admin_user} password: ') if args.admin_password else ''
    name = f'soccs_treasury_test_{secrets.token_hex(4)}'
    try:
        connection = pymysql.connect(host=args.host, port=args.port, user=args.admin_user, password=password, autocommit=True)
    except pymysql.err.OperationalError as error:
        sys.exit(f'Cannot connect to MySQL ({error.args[-1]}). Start MySQL in XAMPP first.')
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    print(f'Created test database {name}')
    try:
        env = dict(os.environ, TEST_DATABASE_URL=f'mysql+pymysql://{quote(args.admin_user)}:{quote(password)}@{args.host}:{args.port}/{name}?charset=utf8mb4')
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *pytest_args], cwd=ROOT, env=env)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS `{name}`')
        connection.close()
        print(f'Dropped test database {name}')
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
