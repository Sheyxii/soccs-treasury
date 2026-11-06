# Regression tests

Run **.\.venv\Scripts\python.exe -m pytest -q** from the repository root.
Tests create temporary migrated SQLite databases with foreign keys and CSRF enabled.

For XAMPP run **.\.venv\Scripts\python.exe scripts/test_mysql.py**. It creates a random
soccs_treasury_test_* database using local root on port 3306 (blank password),
passes its URL to the child tests, and drops only that database in a finally block.
Operational records and grants are untouched. Do not set TREASURY_TEST_DATABASE_URL
to a database you want to retain. Fixtures reject names without the test prefix.

Coverage includes all five roles, CSRF, denied URLs, authentication, sessions,
passwords, CLI maintenance, migrations, exact PHP 250 and 100/75/75 shares for both
programs, pending/rejected/approved accounting, duplicate payments and references,
resubmission, atomic rollback, over-budget authorization and approval-time balance
checks, HTTP collection/receipt/report/verification, member/budget/fee forms,
nonfinite amounts, record ownership, oversight privacy, backup round trip,
integrity, retention, password confirmation and session revocation.

On 17 October 2026 all **66 tests passed on SQLite and XAMPP MariaDB 10.4.32**.
This does not establish measured 80% coverage, load-test targets or officer acceptance.
See docs/implementation.md for remaining acceptance work.
