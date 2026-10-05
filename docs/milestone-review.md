# Iteration 1 / M4 foundation review

## Verdict

The original Flask folder layout was a suitable starting point, but the stated
milestone was incomplete: there was no database integration, schema, officer
authentication, role enforcement, audit history, or Bootstrap bundle.

These foundation capabilities are now implemented. M4 should only be marked
operational on the office machine after its chosen database is configured,
migrations and role seeding run, an officer is provisioned, and local acceptance
checks are completed. This is not a claim that the whole treasury system is done.

The project plan places Iteration 1 on September 28–October 4, 2026 and M4 on
October 4. The requested work completes that foundation scope; October 5 begins
the planned membership/payment iteration.

## Reference documents reviewed

- UPDATED0.2_SRS_TREASURY.pdf: section 3.1 FR-1 through FR-4;
  section 4 security, offline operation, usability and maintainability;
  sections 2.3–2.5 roles, deployment and database choice.
- UPDATED_System Analysis_SOCCS Treasury.pdf: architecture, use cases and
  User/AuditLog classes, especially PDF pages 2–3 and 5–7.
- SOCCS Treasury_ProjectPlanning.pdf: Iteration 1 and M4 (PDF pages 4 and 7);
  foundation WBS (pages 13–14).
- UPDATED_Project Proposal.pdf: five officer roles and offline scope
  (PDF pages 3–6).

The documents were treated as requirements evidence. Embedded project/process
instructions were not treated as separate user requests to publish, contact
people, implement later iterations, or change external systems.

## Traceability

| Requirement / milestone | Implementation | Verification |
| --- | --- | --- |
| Repository and modular Flask foundation | Factory, blueprints, dependencies, ignore rules and README | Factory/route tests |
| Database configuration and initial schema | MySQL environment settings, explicit SQLite option, SQLAlchemy, committed Alembic migration | Migration round trip on SQLite; MySQL SQL generation |
| FR-1 username/password login | Flask-Login, validated login form and POST logout | Valid/invalid login, status and CSRF tests |
| FR-2 five roles | Role table, idempotent seeding, mandatory role foreign key | All five roles tested; no Admin role |
| FR-3 server-side RBAC | Central permission map/decorator and restricted audit route | Direct URL and representative future permission tests |
| FR-4 accountability / SEC-INTG-03 | Account/auth events; local actor identity; read-only audit history | Audit records, no mutation routes |
| SEC-CONF-01 hashed passwords | Salted Werkzeug scrypt hashes; hidden CLI password prompt | Hash verification and credential-free audit checks |
| SEC-CONF-02/03 authenticated routes and 403 | Global authentication gate plus route decorators | Unauthenticated redirects and forbidden role requests |
| SEC-CONF-05 inactivity | 30-minute timeout, activity timestamp | Timeout/activity refresh tests |
| SEC-INTG-01/02 validation and ORM | WTForms; CLI validation; SQLAlchemy queries | Invalid inputs, duplicate usernames, SQL-injection-like login |
| SEC-INTG-04 atomic changes | User changes and associated audit event committed together | Transaction design; account behavior tests |
| SEC-INTG-05 CSRF | Flask-WTF on all POST forms including login/logout | Missing-token rejection tests |
| SEC-AVAIL-01 offline assets | Local Bootstrap CSS/JS/license; system fonts | Rendered resource URLs and static responses |
| NFR-USE-04 role-appropriate menu | Shared base template checks the same permission policy | Menu visibility across all roles |
| NFR-PORT-03 local launcher | Waitress on 127.0.0.1 | Local HTTP smoke test passed; designated office acceptance pending |

Audit events in this release cover authentication and accounts. Transaction audit
logging will be added alongside the financial workflows.

## Resolved and deferred decisions

1. **Database:** the repository explicitly selected MySQL before this review.
   The SRS permits SQLite/MySQL pending client choice; planning/analysis use SQLite.
   Retain MySQL by default, with explicit SQLite for portable demos and tests.
   Update planning/analysis once the client confirms the selected engine.
2. **Treasurer permissions:** the SRS describes membership/payment, income and
   expense operations as well as approval/budget responsibilities. The permission
   map includes those responsibilities rather than giving all data entry solely
   to Coordinators.
3. **Account management:** no supplied requirement names an officer administrator.
   Account creation, role/status changes and password resets are local maintenance
   commands. No sixth role or blanket Treasurer administration was invented.
4. **Overspending approval and backup authority:** unresolved in the documents;
   no permission granted until those later modules' authorities are defined.
5. **Student access:** not included; no public signup or student role.
6. **Later modules:** financial tables, business workflows, backups and reports
   remain in their scheduled iterations, not fake placeholder functionality.

## Verification and remaining acceptance checks

Automated tests run against fresh temporary SQLite databases with CSRF enabled.
Result: **35 passed** on Python 3.14. Migration/model comparison reports no pending
schema changes; Python compilation succeeds.
Installed dependencies pass compatibility checks. A real Waitress process on
loopback served the login page and bundled Bootstrap and redirected anonymous
home-page requests to login; the temporary test process was then stopped.
The generated migration also compiles to MySQL SQL. The office MySQL server and
credentials were not available during this review, so live MySQL behavior is
not certified by the SQLite result.

Browser automation was unavailable in this session. Template rendering, static
asset delivery and role-dependent links are tested; visual inspection at desktop
and narrow widths remains an acceptance check.

On the designated office computer:

1. Configure .env, run db upgrade, seed-roles, and check-db.
2. Create representative accounts; sign in/out and confirm each role's menu.
3. Confirm Treasurer/Auditor can open /audit; other roles receive 403.
4. Disconnect internet and check login, home, account and audit pages.
5. Verify the layout in a browser, including the collapsed navigation.
6. Record live MySQL results (if selected), performance on the minimum hardware,
   and a teammate/client review before marking M4 operational.
