# Black-box testing report

Test date: 6 November 2026.

## Scope and approach

The dedicated suite in `tests/test_blackbox.py` treats the app as an HTTP service.
It submits the real forms, obtains CSRF tokens and record identifiers from rendered
HTML, and checks observable responses and exported records. It does not inspect
database models or invoke posting, approval, or backup business functions.

The shared fixture creates a temporary migrated database and five test officer
accounts. All financial setup then goes through the website: academic-year setup,
member registration, budget creation, and category allocation. Backup tests store
files in a separate temporary directory. The scenarios do not use office records.

## Scenario matrix

| Area | Cases | Inputs/actions and expected result |
| --- | ---: | --- |
| Five officer roles | 5 | Test real pages for Treasurer, Coordinator, Auditor, President, and Adviser. Deny unauthorized approval, backup creation, and budget changes; accounts remain unchanged. |
| Pending payment completion | 1 | Coordinator submits; Treasurer records receipt of payment against the same request. Student becomes Paid, totals show PHP 250 split 100/75/75, HTML/PDF receipt works, Auditor verifies, repeat payment is rejected. |
| Rejection and resubmission | 1 | Reject requires a reason, rejected payment affects no totals, corrected request can reuse its released reference, old rejected request cannot be approved. |
| Invalid payment inputs | 13 | Zero, negative, partial, excessive decimal precision, NaN, infinity, nonnumeric amount, missing/short GCash reference, unknown member/year, blank description, and malformed date leave the pending request and accounts unchanged. A corrected submission succeeds. |
| Duplicate submissions/references | 1 | Replaying a form posts only once. GCash reference collision leaves an existing payment pending and preserves report totals. |
| Budget workflow | 1 | Over-budget request remains pending until approval includes a reason. Allocation cannot fall below posted spending. Closed budgets block new expenses; reopening enables them. |
| CSRF protection | 6 | POST without a token to members, fee settings, budgets, payments, backups, and logout is rejected without changing account totals or ending the session. |
| Search and exports | 1 | User-provided HTML is escaped in pages, CSV formula-like text is escaped, special-character searches work, and invalid report dates/missing filters produce 400/404 responses. |
| Backup recovery | 1 | Create, download, and import a valid backup. Wrong restore password preserves records. Valid restore returns report totals to the saved state and revokes every officer session. |
| Invalid backup import | 5 | Non-JSON text, empty object, array, invalid encoding, and incorrect signature are rejected while existing financial records remain intact. |
| Empty installation and errors | 1 | Main pages work without financial records, payment setup guidance appears, missing records return 404, and health responds successfully. |
| **Total** | **36** | **Dedicated HTTP black-box cases.** |

The existing regression suite supplements these cases with authentication and
password changes, CLI account maintenance, migrations, session expiry, member
deletion, transaction ownership, accounting rollback, pagination, receipt content,
and page-link crawling for all five roles.

## Recorded results

- Dedicated black-box suite on SQLite: **36 passed**, 77.43 seconds.
- Combined acceptance/regression suite on SQLite: **135 passed**, 204.32 seconds
  (36 black-box cases plus 99 existing regression cases), with no failures or errors.
- XAMPP/MariaDB: **not run**. The helper could not connect to `127.0.0.1:3306`
  because the connection was refused. No MySQL test database was created.

Machine-readable results are written locally to `output/blackbox-first.xml` and
`output/blackbox-full.xml`. Generated output is not part of the test source.

## Repeatable commands

From the repository root, using the installed virtual environment:

```powershell
# Dedicated black-box scenarios
.\.venv\Scripts\python.exe -m pytest -m blackbox -q -p no:cacheprovider

# All regression and black-box scenarios, with a JUnit report
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --junitxml=output/test-results.xml

# Disposable MySQL database; start XAMPP MySQL first
.\.venv\Scripts\python.exe scripts/test_mysql.py -m blackbox
```

## Limits and remaining checks

These are HTTP acceptance tests using Flask's test client. They do not execute
browser JavaScript or assess visual layout, keyboard/screen-reader behavior,
browser printing, or download handling in a real browser. The actual Waitress
process, Windows launchers, reverse proxy/HTTPS deployment, and load/concurrent
request behavior are outside this run.

Before office acceptance, also verify interactive search and form behavior in the
supported browsers, print a receipt with the office printer, and run the suite
against XAMPP/MariaDB. Passing these cases is not a claim of exhaustive coverage,
measured code coverage, or an independent security audit.
