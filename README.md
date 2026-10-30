# SOCCS Treasury

A standalone, offline office website for membership collections, approvals, budgets,
expenses, reports and receipts. Built with **Flask, SQLAlchemy ORM, MySQL/MariaDB
(XAMPP), Waitress and locally bundled Bootstrap 5.3.8**, with a responsive purple workspace.

## Use this installation

1. Start **MySQL** in XAMPP. Apache is not required.
2. Double-click **Start-Treasury.cmd** in this folder. It checks the database, then opens
   **http://127.0.0.1:5000** in your browser.
3. Sign in with your existing officer account.
4. As Treasurer, open **Fee settings** and create the academic year with the actual
   collection dates. Then add members and create budgets with category allocations.

Keep the launcher open while using the app. Stop with Ctrl+C, then stop MySQL from
XAMPP before shutting down Windows. Run one app process only. Stop the app before
schema upgrades or local account maintenance.

Existing officer passwords were preserved. There is no production default password.
The existing treasurer account remains available; the local custodian can reset a
forgotten password using the command below.

## Confirmed financial rules

- **PHP 250 per student per academic year:** PHP 100 SOCCS, PHP 75 ITUH and PHP 75 CSS
  for both IT and CS students. This user-confirmed rule supersedes the earlier
  documents' program-specific split.
- Treasurer records post immediately unless over budget. Coordinator requests stay
  Pending until Treasurer approval. Rejection requires a reason.
- Pending and rejected records do not change funds or budget spending. Pending
  membership requests reserve the member/year; rejection releases the reservation.
- Over-budget expenses require **explicit Treasurer approval and an explanation**.
  Category availability is checked again when approving.
- Water-refilling income belongs to SOCCS. Available SOCCS funds exclude the ITUH
  and CSS shares. Allocating a budget plans spending; it does not move cash.
- GCash is recorded and verified manually. The app neither connects to GCash nor moves money.
- Academic-year fee rules are preserved once created. Posted records cannot be
  edited or deleted through the website. Partial membership payments are unsupported.

## Officer access

| Role | Available work |
| --- | --- |
| Treasurer | Members, payments, decisions, budgets, income, expenses, reports, verification, audit, fee setup, backup/restore |
| Coordinator | Manage members, submit payments/expenses, view own requests and member payment status |
| Auditor | Read member/financial records, verify posted payments, view budgets, reports and audit |
| President / Adviser | Financial dashboard and reports |

All officers can change their own password. Account provisioning remains a trusted
local command because the requirements do not assign account administration to an
officer role. No student logins or public registration are included.

## New Windows installation

Use Python 3.11+ and MySQL/MariaDB with InnoDB and enforced CHECK constraints.
Verified with Python 3.14 and XAMPP MariaDB 10.4.32. Install dependencies once while
online; normal operation requires no internet connection.

From this folder in PowerShell:

~~~powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
~~~

Set SECRET_KEY in .env to the generated value, and configure MYSQL_HOST,
MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER and MYSQL_PASSWORD for a dedicated app
database/account. Preserve an existing .env. Keep a secure copy of SECRET_KEY:
saved backups require their original signing key. Never commit secrets or records.

After starting XAMPP MySQL:

~~~powershell
.\.venv\Scripts\python.exe scripts/setup_xampp.py
.\.venv\Scripts\python.exe scripts/upgrade_database.py
.\.venv\Scripts\python.exe -m flask --app app seed-roles
.\.venv\Scripts\python.exe -m flask --app app check-db
.\.venv\Scripts\python.exe -m flask --app app create-user --username treasurer --full-name "SOCCS Treasurer" --role Treasurer
.\.venv\Scripts\python.exe run.py
~~~

The setup helper uses local root only to create the configured database and grant
database-scoped permissions. If root has a password, add --admin-password to
scripts/setup_xampp.py; it prompts securely. It does not change existing passwords.
The running app uses the dedicated .env account.

Migrations are versioned; do not run db init again. The upgrade helper saves raw
pre-upgrade data under instance/pre-upgrade before migrating. This engineering
snapshot is not an importable app backup.

Waitress listens on **127.0.0.1:5000** by default (HOST, PORT and THREADS in .env).
Run one app process only: financial operations and backup/restore are serialized inside it.
Warnings and errors are written to instance/logs/treasury.log (rotated automatically).

## Going online later

The same code can be put on a server without changes; only .env differs.

1. Use a MySQL/MariaDB server (set the MYSQL_* values, or a full DATABASE_URL).
2. Put a reverse proxy with HTTPS (Nginx, Caddy or IIS) in front of `python run.py`.
   Keep HOST=127.0.0.1 so only the proxy can reach the app.
3. In .env set `SESSION_COOKIE_SECURE=true` and `TRUST_PROXY=1`.
4. Point the proxy's health check at **/health** (returns `{"status": "ok"}`; no data shown).
5. Keep one app process. Sign-in attempts are limited per account
   (LOGIN_MAX_ATTEMPTS / LOGIN_LOCK_MINUTES), sessions end after SESSION_TIMEOUT_MINUTES of
   inactivity, and pages are sent with a strict Content-Security-Policy.

## Daily workflow

1. **Members:** add student number (format 1234-5678), name, program, year and section.
   Search/filter by program, academic year and payment status. Deactivate members who leave;
   an inactive member with no payment records can be deleted, while members with records stay
   inactive to preserve history.
2. **Payments:** select the member/year, enter date, amount and method. Verify GCash
   evidence manually and enter its reference. Duplicate annual payments and reused
   incoming GCash references are blocked.
3. **Review:** Treasurer checks Pending records and approves or rejects. Approval
   creates the payment, income and numbered receipt together.
4. **Budgets/expenses:** create semester/event budgets and category allocations.
   Record each expense with date, purpose and receipt/reference. Utilization is
   highlighted from 80%; overspending is held for approval.
5. **Close finished budgets** from the budget page. Closed budgets stay in reports but
   are no longer offered for new expenses; they can be reopened.
6. **Reports:** select dates and optional budget scope; export CSV or use the browser's
   Print / Save PDF. Budget filters restrict expenses; income remains organization-wide
   and is labeled accordingly. Annual membership counts use the selected academic
   year, independently of the financial date filter.
7. **Receipts:** open an approved payment and select View receipt. Receipts retain
   the student's identity as recorded at payment time.

## Backups and recovery

The Treasurer can create, download, import and restore signed JSON snapshots from
**Backups**. The four most recent are retained under instance/backups. Weekly backup
runs on the first authenticated visit when the latest snapshot is at least seven
days old. It cannot run while the app/computer is off. Failures show a Treasurer warning.

Snapshots contain member records, officer accounts and finances. Signing detects
modification; it does **not encrypt** the file. Keep downloaded copies and the
original SECRET_KEY securely on separate storage.

To restore, enter RESTORE and the current Treasurer password. All current records
are replaced. The app validates the snapshot and first saves a recovery copy, then
restores in a database transaction. Successful restoration revokes every officer
session. Sign in with an account from the restored snapshot.

On another PC, install the same app version and dependencies, use the original
SECRET_KEY in the new .env, initialize migrations and a temporary Treasurer account,
then import and restore. New database credentials may differ. App restore does not
change XAMPP's database users or server permissions.

## Local account maintenance

Use a 12–128 character password. Changes are audited and revoke existing sessions.

~~~powershell
.\.venv\Scripts\python.exe -m flask --app app list-users
.\.venv\Scripts\python.exe -m flask --app app create-user --username coordinator --full-name "Coordinator Name" --role Coordinator
.\.venv\Scripts\python.exe -m flask --app app reset-password treasurer
.\.venv\Scripts\python.exe -m flask --app app set-user-role coordinator Auditor
.\.venv\Scripts\python.exe -m flask --app app set-user-status coordinator inactive
~~~

## Tests and preview

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/test_mysql.py
.\.venv\Scripts\python.exe -m flask --app app db check
.\.venv\Scripts\python.exe scripts/preview.py
~~~

Tests use disposable databases. The MySQL helper creates a random
soccs_treasury_test_* database and removes only that generated database afterward.
It assumes local XAMPP root with a blank password on port 3306. Never point test
fixtures at operational data. See [tests/README.md](tests/README.md).

The sample preview (double-click **Start-Preview.cmd**) runs at **http://127.0.0.1:5001**
in a separate SQLite database that is rebuilt on every start, and displays a sample-data banner. Usernames: treasurer, coordinator, auditor,
president, adviser. Their preview-only password is **Preview-only-2026!**.
These credentials do not apply to the real app.

## Project map

| Path | Purpose |
| --- | --- |
| app/finance/ | Membership, posting/review, budgets, reports, fee policies |
| app/models/ | SQLAlchemy models and constraints |
| app/backups.py | Snapshot signing, retention and restoration |
| app/auth/, app/users/, app/permissions.py | Authentication and authorization |
| app/templates/, app/static/ | Purple Bootstrap workspace, offline assets, print layouts |
| migrations/ | Versioned schema |
| scripts/ | Setup, pre-upgrade snapshot, preview and isolated MySQL tests |
| tests/ | Regression and workflow tests |
| docs/implementation.md | Decisions, verification and remaining officer acceptance |

Original login artwork and custom styles were retained.
