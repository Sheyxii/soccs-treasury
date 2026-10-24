"""Run tests in a randomly named disposable XAMPP database; production is untouched."""
import os
import secrets
import subprocess
import sys
import pymysql

name = 'soccs_treasury_test_' + secrets.token_hex(6)
connection = pymysql.connect(host='127.0.0.1',user='root',autocommit=True)
try:
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    environment = dict(os.environ, TREASURY_TEST_DATABASE_URL=f'mysql+pymysql://root@127.0.0.1/{name}?charset=utf8mb4')
    result = subprocess.run([sys.executable,'-m','pytest','-q','-x',*sys.argv[1:]],env=environment)
finally:
    # The name is generated locally above and never read from arguments or configuration.
    with connection.cursor() as cursor:
        cursor.execute(f'DROP DATABASE `{name}`')
    connection.close()
sys.exit(result.returncode)
