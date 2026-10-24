"""Create/grant only the configured app database, using local XAMPP administration.

Run from the repository root. Existing app accounts/passwords are not altered.
Use --admin-password to prompt when XAMPP's root account has a password.
"""
import argparse
import getpass
import os
import re
from pathlib import Path
import pymysql
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--admin-password', action='store_true')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    name = os.environ.get('MYSQL_DATABASE', 'soccs_treasury_dev')
    user = os.environ.get('MYSQL_USER', 'soccs_app')
    password = os.environ.get('MYSQL_PASSWORD', '')
    if not re.fullmatch(r'[A-Za-z0-9_]+', name) or user == 'root':
        raise SystemExit('Use a simple database name and a dedicated app user in .env.')
    connection = pymysql.connect(host='127.0.0.1', port=int(os.environ.get('MYSQL_PORT', 3306)),
                                 user='root', password=getpass.getpass('XAMPP root password: ') if args.admin_password else '', autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        cursor.execute('CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s', (user, '127.0.0.1', password))
        cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES ON `{name}`.* TO %s@%s', (user, '127.0.0.1'))
    connection.close()
    print(f'Local database {name} and database-scoped grants are ready. No existing password was changed.')


if __name__ == '__main__':
    main()
