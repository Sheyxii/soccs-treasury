# Tests

Authentication and RBAC tests will be introduced with those features.
Test against a separate MySQL test database, never the operational database.

Required scenarios include valid and invalid login, inactive accounts, logout,
all five roles, unauthorized direct requests, CSRF checks, and safe audit events.
