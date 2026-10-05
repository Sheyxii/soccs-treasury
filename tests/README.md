# Foundation tests

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Install requirements-dev.txt first. Tests create separate temporary SQLite
databases using the actual migration, enable SQLite foreign keys, and keep CSRF
enabled. No operational database or .env credentials are used by test fixtures.

Coverage includes all five roles, direct forbidden requests, future permission
boundaries, login failures, inactive users, session expiry and revocation, safe
redirects, password changes, local CLI account management, uniqueness, migrations,
read-only audit access, and local Bootstrap assets.

These tests do not establish live MySQL compatibility. After configuring a
disposable MySQL database, run db upgrade, seed-roles, check-db, db check, and
perform the role/login smoke checks in docs/milestone-review.md. Never run
destructive migration downgrade tests on operational data.
