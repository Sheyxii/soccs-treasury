# Implementation and verification record

## Scope and decisions

The proposal, project-planning PDF, Gantt workbook, updated SRS and system-analysis
PDF were reviewed as requirements evidence. Embedded instructions did not authorize
unrelated actions. The user expanded the earlier foundation milestone to the full
standalone app and selected Flask, SQLAlchemy, Waitress, Bootstrap and XAMPP MySQL.
The M4 review is retained as historical context.

Confirmed rules: PHP 250 per student per academic year, divided into PHP 100 SOCCS,
PHP 75 ITUH and PHP 75 CSS for both programs. Treasurer approves overspending and
manages backups. Actual academic-year dates are entered through Fee settings.
The earlier program-specific split in the documents is superseded by this user decision.

Annual policies store 40/30/30 percent and snapshot the payment rules. CSS receives
the cent remainder after rounding SOCCS/ITUH, preserving the exact total. At PHP 250,
the shares are exactly 100/75/75. Programs still classify members and payment history.

## Requirement mapping

| Area | Delivered behavior | Verification |
| --- | --- | --- |
| Authentication / roles | Five roles, hashed passwords, CSRF, session expiry/revocation, route and record authorization | Foundation and role tests |
| Members | Add/edit/search/filter/deactivate, annual payment status and history | Form/permission tests; browser review |
| Payments | Cash/GCash, once/year, full fee, manual verification | Service and HTTP tests |
| Requests | Pending, approval/rejection, actor/timestamps/remarks and audit | Workflow, ownership and rollback tests |
| Budgets | Semester/event categories, allocation/spent/remaining, 80% indication | Form and expense tests |
| Overspending | Hold pending, Treasurer explanation, approval-time balance recheck | Overspending and changed-balance tests |
| Income / shares | Membership and water collections; separate SOCCS/ITUH/CSS totals | Exact Decimal tests |
| Expenses | Category/date/purpose/reference and controlled posting | Posting/rollback tests |
| Dashboard / reports | Cash-basis totals, six-month chart, category utilization, date/scope filters, CSV, print/PDF | Report tests and browser review |
| Receipts | Unique IDs, retained student identity, print layout | Receipt/atomicity tests |
| Backups | Signed JSON, four retained, weekly-on-use/on-demand, import/restore, recovery snapshot | Round-trip/integrity/retention/HTTP tests |
| Offline deployment | Local assets, localhost Waitress, Windows launcher | Asset tests and local server checks |

Payments, receipts and income/expense records commit atomically. Official entries
cannot be edited/deleted through the UI. Database uniqueness supplements service
validation. A single-process office lock protects workflows from interleaving with
backup/restore. Direct database edits and multiple server processes are unsupported.

The review-before-posting interaction was compared with
[Odoo's expense approval workflow](https://www.odoo.com/documentation/17.0/applications/finance/expenses/approve_expenses.html)
and [Zoho Spend/Books](https://www.zoho.com/us/spend/help/admin/integrations/zoho-books/).
SOCCS's own confirmed roles and policies govern this implementation.

## Verification on 17 October 2026

- All 66 regression tests passed on SQLite in 83.60 seconds.
- All 66 passed on XAMPP MariaDB 10.4.32 in 98.64 seconds.
- Existing MySQL officer accounts were preserved. All treasury tables passed the
  database integrity check. No sample financial/member records were inserted into
  the real database.
- Browser review uses the separate sample SQLite preview.
- Browser checks covered payment approval, exact shares, receipt rendering,
  overspending warnings, sample backup creation, and layouts at 300, 390, 1024
  and 1440 pixels. The preview uses a distinct cookie, signing key and backup folder.
- The real installation awaits actual academic-year dates and member/budget data.

Before office turnover, rehearse collection/rejection/approval with the officers,
check the office printer, reconcile opening balances, and perform a recovery drill
on a spare installation using an external backup. Cross-browser Chrome/Edge/Firefox
coverage, measured code-coverage percentage, large-volume timing targets, power-loss
simulation and formal security audit are not claimed by this delivery.

## XAMPP recovery record

Startup failed due to a missing checkpoint in the Aria log; the database-permissions
table also had truncated pages. A full hash-verified copy of 167 database files was
saved under instance/mysql-recovery-20261017-201911/original before repair.
The numbered Aria log was quarantined. aria_log_control and InnoDB data files were
preserved. Aria repair was first tested on copies, then reconciled through the running
server. One unrecoverable SOCCS permission row was recreated. Every table passed
mysqlcheck, followed by a clean shutdown/restart and successful app connection.

An earlier repair discarded four corrupted database-permission rows. SOCCS's scoped
access was restored; unrelated local projects may need their grants reviewed. No
treasury record table was replaced during the Aria repair. Keep the recovery folder
until this installation and other XAMPP projects are confirmed healthy. Inspect and
back up future failures before repair; do not replace the data directory or remove
InnoDB files as a generic fix.

Recovery followed [MariaDB Aria guidance](https://mariadb.com/docs/server/server-usage/storage-engines/aria/aria-faq)
and [aria_chk's requirement to stop the server](https://mariadb.com/docs/server/clients-and-utilities/aria-clients-and-utilities/aria_chk)
before offline repair.
