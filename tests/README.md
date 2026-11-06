# Regression tests

Run **.\.venv\Scripts\python.exe -m pytest -q** from the repository root.
Tests create temporary migrated SQLite databases with foreign keys and CSRF enabled.

## Black-box acceptance tests

Run the dedicated HTTP acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -m blackbox -q -p no:cacheprovider
```

Run both acceptance and existing regression tests, saving a JUnit report:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --junitxml=output/test-results.xml
```

`test_blackbox.py` creates financial records through actual forms with CSRF enabled.
It checks pages, redirects, search responses, CSV exports, PDF downloads, and backup
recovery without querying models or calling business services. Each case uses an
isolated database; backup scenarios also use a temporary backup directory. The
shared fixture provisions test officer accounts before the scenarios begin.

See [the black-box test report](../docs/black-box-testing.md) for the scenario
matrix, recorded results, and limits of these automated checks.

## Database compatibility and existing coverage

For XAMPP run **.\.venv\Scripts\python.exe scripts/test_mysql.py**. It creates a random
soccs_treasury_test_* database using local root on port 3306 (blank password),
passes its URL to the child tests, and drops only that database in a finally block.
Operational records and grants are untouched by the helper. It sets
`TEST_DATABASE_URL` for the generated database; do not point that variable at an
existing office database because the fixtures drop test tables after each test.

To run only black-box cases on XAMPP after starting MySQL:

```powershell
.\.venv\Scripts\python.exe scripts/test_mysql.py -m blackbox
```

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
