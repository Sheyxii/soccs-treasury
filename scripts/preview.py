"""Sample-data preview on http://127.0.0.1:5001, separate from the office database.

Rebuilds instance/preview.sqlite3 on every start. Never touches MySQL or .env data.
Usage: .venv\\Scripts\\python.exe scripts/preview.py
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask_migrate import upgrade  # noqa: E402
from waitress import serve  # noqa: E402
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import AcademicYear, Budget, BudgetCategory, Member, Role, User  # noqa: E402
from app.permissions import ROLE_PERMISSIONS  # noqa: E402

PASSWORD = "Preview-only-2026!"
PORT = 5001

MEMBERS = [
    ("2024-0001", "Juan Dela Cruz", "IT", 3, "A"),
    ("2024-0002", "Maria Santos", "CS", 3, "A"),
    ("2025-0003", "Jose Reyes", "IT", 2, "B"),
    ("2025-0004", "Ana Bautista", "CS", 2, "A"),
    ("2026-0005", "Carlo Mendoza", "IT", 1, "C"),
    ("2026-0006", "Liza Garcia", "CS", 1, "B"),
]


def build(app):
    with app.app_context():
        upgrade(directory=str(ROOT / "migrations"))
        for name in ROLE_PERMISSIONS:
            role = Role(name=name)
            user = User(username=name.lower(), full_name=f"Sample {name}", role=role)
            user.set_password(PASSWORD)
            db.session.add_all([role, user])
        db.session.add(AcademicYear(
            name="2026-2027", starts_on=date(2026, 8, 1), ends_on=date(2027, 5, 31),
            fee=Decimal("250.00"), soccs_percent=Decimal("40.00"),
            ituh_percent=Decimal("30.00"), css_percent=Decimal("30.00")))
        for number, name, program, year, section in MEMBERS:
            db.session.add(Member(student_number=number, full_name=name, program=program,
                                  year_level=year, section=section))
        db.session.add(Member(student_number="2022-0007", full_name="Mark Villanueva", program="IT",
                              year_level=4, section="A", active=False))  # inactive, no records: can be deleted
        budget = Budget(name="1st Semester 2026-2027", kind="Semester",
                        starts_on=date(2026, 8, 1), ends_on=date(2026, 12, 20))
        db.session.add(budget)
        for name, amount in (("Events", "3000.00"), ("Supplies", "1500.00"), ("Water refilling", "1000.00")):
            db.session.add(BudgetCategory(budget=budget, name=name, allocated=Decimal(amount)))
        db.session.commit()
        add_sample_activity()


def add_sample_activity():
    """Posted payments, income and expenses so the dashboard has something to show."""
    from secrets import token_hex
    from app.finance.services import submit_transaction
    users = {u.username: u for u in db.session.scalars(db.select(User))}
    year = db.session.scalar(db.select(AcademicYear))
    members = db.session.scalars(db.select(Member).order_by(Member.id)).all()
    categories = {c.name: c for c in db.session.scalars(db.select(BudgetCategory))}

    def submit(actor, kind, amount, day, description, **extra):
        submit_transaction(users[actor], kind=kind, amount=Decimal(amount), occurred_on=day, description=description,
                           submission_key=token_hex(24), method=extra.pop("method", "Cash"),
                           reference=extra.pop("reference", ""), **extra)

    paid_on = [date(2026, 8, 12), date(2026, 8, 20), date(2026, 9, 3), date(2026, 9, 18), date(2026, 10, 7)]
    for member, day in zip(members[:5], paid_on):
        submit("treasurer", "Payment", "250.00", day, "Annual membership fee", member_id=member.id, academic_year_id=year.id)
    for day, amount in ((date(2026, 8, 30), "420.00"), (date(2026, 9, 29), "515.00"), (date(2026, 10, 28), "460.00")):
        submit("treasurer", "Income", amount, day, "Water refilling station collection")
    for name, day, amount, ref, text in (("Supplies", date(2026, 8, 25), "380.00", "OR-1021", "Printer ink and bond paper"),
                                         ("Events", date(2026, 9, 22), "1250.00", "OR-1088", "Acquaintance party snacks"),
                                         ("Water refilling", date(2026, 10, 15), "850.00", "OR-1130", "Water gallons restock")):
        submit("treasurer", "Expense", amount, day, text, reference=ref, category_id=categories[name].id)
    submit("coordinator", "Payment", "250.00", date(2026, 10, 27), "Annual membership fee",
           member_id=members[5].id, academic_year_id=year.id)
    db.session.commit()


def main():
    instance = ROOT / "instance"
    instance.mkdir(exist_ok=True)
    database = instance / "preview.sqlite3"
    database.unlink(missing_ok=True)
    app = create_app({
        "SECRET_KEY": "preview-only-secret-key-not-for-office-data-0000",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + database.as_posix(),
        "BACKUP_DIRECTORY": str(instance / "preview-backups"),
        "DEMO_MODE": True,
    })
    build(app)
    print(f"Sample preview: http://127.0.0.1:{PORT}")
    print(f"Usernames: {', '.join(n.lower() for n in ROLE_PERMISSIONS)}  Password: {PASSWORD}")
    print("Press Ctrl+C to stop.")
    serve(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
