# SOCCS Treasury

Offline office application for the Student Organization of the College of Computer
Studies. This release implements the **Iteration 1 / M4 foundation**: Flask
structure, database configuration and migrations, officer accounts, five roles,
authentication, server-side RBAC, and a locally bundled Bootstrap layout.

The original repository was a landing-page scaffold. See
[the milestone review](docs/milestone-review.md) for requirements, corrections,
scope decisions, and remaining acceptance checks.

## Implemented

- Application factory with auth, users, and main blueprints.
- SQLAlchemy models for roles, officer users, and audit events; versioned migration.
- Username/password login, salted Werkzeug password hashes, CSRF-protected POST
  logout, and a 30-minute inactivity timeout.
- Account status checks on every request; password, role, and status changes
  invalidate existing sessions.
- Coordinator, Treasurer, Auditor, President, and Adviser roles with a shared
  deny-by-default permission policy. Audit history is restricted to Treasurer
  and Auditor. Each officer can access their own account and change their password.
- Trusted local CLI provisioning, role changes, activation/deactivation, password
  resets, and audit entries stored atomically with account changes.
- Bootstrap 5.3.8 CSS and JavaScript stored locally, including its MIT license.
  No CDN, web fonts, public registration, student accounts, or extra admin role.
- Waitress launcher bound to 127.0.0.1.

Membership records, payments, transaction approvals, budgets, income, expenses,
receipts, financial dashboards/reports, and backup/restore are later iterations.
The home page labels this foundation release and does not show invented financial
figures or links to unimplemented modules.

## Windows setup

Use Python 3.11 or newer. Verified here with Python 3.14. Install dependencies once
while online (or from a prepared wheel collection); normal operation is offline.

From the repository directory in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated value in `SECRET_KEY` in `.env`. Startup rejects missing/short
secrets. Preserve existing configuration; never commit `.env` or credentials.
For an environment without pip, the alternative is:
`uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt`.

### Database choice

**MySQL is the repository default.** The revised SRS permits SQLite or MySQL;
the planning and analysis documents originally use SQLite. This implementation
retains the repository's existing MySQL decision. Record client confirmation of
the selected engine in your project documents.

Install/start a local MySQL server with InnoDB and enforced CHECK constraints.
Using your local MySQL administrator, create a dedicated development database and
a database-scoped development account. Replace the example password:

```sql
CREATE DATABASE soccs_treasury_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'soccs_app'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_A_LOCAL_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
ON soccs_treasury_dev.* TO 'soccs_app'@'127.0.0.1';
```

These are development/migration privileges, scoped to this database. For turnover,
use a separate migration account and a restricted runtime account (SELECT on
roles; SELECT/INSERT/UPDATE on users; SELECT/INSERT on audit_logs). Extend grants
deliberately as future modules are added. Never use the MySQL root account as the
application's runtime login.

Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and
`MYSQL_PASSWORD` in `.env`. Individual settings safely handle special characters
in passwords. Bind the database server to loopback as well.

For an **explicit SQLite-only demo**, set this instead in `.env`:

```dotenv
DATABASE_URL=sqlite:///soccs_treasury_dev.sqlite3
```

It stores the database under the ignored `instance/` folder, outside static files.
`DATABASE_URL` overrides the MySQL fields. There is no silent fallback from a
failed MySQL connection. SQLite testing does not verify a live MySQL installation.

### Initialize and run

After configuring the chosen database:

```powershell
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\.venv\Scripts\python.exe -m flask --app app seed-roles
.\.venv\Scripts\python.exe -m flask --app app check-db
.\.venv\Scripts\python.exe -m flask --app app create-user --username treasurer --full-name "SOCCS Treasurer" --role Treasurer
.\.venv\Scripts\python.exe run.py
```

The account command prompts for a password twice without displaying it. There are
no default credentials. Use a 12–128 character password. Create each authorized
officer separately using one of the five role names (case-sensitive).

Open http://127.0.0.1:5000 and sign in. Stop with Ctrl+C. This launcher works offline
and never enables debug mode. For development only:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --debug --host 127.0.0.1
```

Do not bind to 0.0.0.0 or expose the office application to the internet.
The localhost HTTP configuration uses HttpOnly and SameSite=Lax cookies.
If the deployment is moved to HTTPS, enable SESSION_COOKIE_SECURE.

### Local account maintenance

The documents do not assign officer-account administration to a role. Maintenance
therefore requires trusted access to the office computer and its terminal, pending
client confirmation. An OS username is recorded as the local audit actor.
Protect the OS account and application/database files accordingly.

```powershell
.\.venv\Scripts\python.exe -m flask --app app list-users
.\.venv\Scripts\python.exe -m flask --app app set-user-role coordinator Auditor
.\.venv\Scripts\python.exe -m flask --app app set-user-status coordinator inactive
.\.venv\Scripts\python.exe -m flask --app app set-user-status coordinator active
.\.venv\Scripts\python.exe -m flask --app app reset-password coordinator
```

Role/status/password changes require a fresh login. Student/member records are
separate from officer identities. There is no account deletion or audit editing UI.

## Permission boundaries

| Role | Foundation pages | Future functional permissions |
| --- | --- | --- |
| Coordinator | Home, own account | Manage members; submit payments/expenses; view own requests |
| Treasurer | Home, own account, audit history | Membership/payment operations, transaction review, budgets, income, expenses, dashboard/reports |
| Auditor | Home, own account, audit history | Verify payment status; read financial records/budgets/reports |
| President | Home, own account | Read dashboard/reports |
| Adviser | Home, own account | Read dashboard/reports |

Future routes must apply `@permission_required("permission.name")` from
`app/permissions.py` and enforce record-level ownership where applicable.
Showing/hiding a link is not authorization. No role currently has overspending
approval, account administration, or backup/restore permissions; those authorities
need definition before the corresponding modules are implemented.

## Tests and migrations

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m flask --app app db check
```

Tests use temporary SQLite databases and the committed migration, not operational
data. They exercise all roles, permission denial, CSRF, login failures, password
changes, session expiry/revocation, CLI provisioning, migration upgrade/downgrade,
uniqueness, audit logging, and locally served assets. See [tests/README.md](tests/README.md).

The initial migration is committed. Do **not** run `db init` again.
For a future model change, use `db migrate -m "Describe the change"`, inspect the
generated migration, test against a disposable database, then run `db upgrade`.
Back up an existing operational database before schema changes.

## Repository map

| Path | Purpose |
| --- | --- |
| app/__init__.py | Factory, session checks, error pages and response headers |
| app/extensions.py | SQLAlchemy, migrations, Flask-Login and CSRF |
| app/models/ | Roles, users and audit models |
| app/permissions.py | Central role policy and route decorator |
| app/auth/ | Login and logout |
| app/users/ | Own account and password changes |
| app/main/ | Home and restricted audit history |
| app/cli.py | Trusted local account/database maintenance |
| app/templates/ | Bootstrap base layout and pages |
| app/static/vendor/bootstrap/ | Local Bootstrap assets and license |
| migrations/ | Versioned database schema |
| tests/ | Disposable-database behavior tests |
| config.py, .env.example | Environment configuration |
| run.py | Local Waitress launcher |
| docs/milestone-review.md | Requirements review and acceptance record |

The repository files were untracked when reviewed. Review them and make your
initial Git commit when ready. No remote publication is performed by setup.
