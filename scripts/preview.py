"""Isolated sample-data preview. Never connects to the configured MySQL database."""
import sys
import secrets
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.extensions import db
from app.models import Role, User, AcademicYear, Member, Budget, BudgetCategory
from app.permissions import ROLE_PERMISSIONS
from app.finance.services import today, submit_transaction, decide_transaction
from flask_migrate import upgrade
from waitress import serve

app = create_app({
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///preview-only.sqlite3',
    'SECRET_KEY': 'sample-preview-only-not-for-real-accounts-2026',
    'SESSION_COOKIE_NAME': 'soccs_preview_session',
    'BACKUP_DIRECTORY': str(Path(__file__).resolve().parents[1] / 'instance' / 'preview-backups'),
    'AUTO_BACKUP': False,
    'DEMO_MODE': True,
})
with app.app_context():
    upgrade()
    if not db.session.scalar(db.select(User.id)):
        users = {}
        for name in ROLE_PERMISSIONS:
            role = Role(name=name)
            user = User(username=name.lower(), full_name='Demo ' + name, role=role)
            user.set_password('Preview-only-2026!')
            db.session.add_all([role, user])
            users[name] = user
        this_year = today().year
        year = AcademicYear(name=f'{this_year}-{this_year+1}', starts_on=date(this_year,1,1), ends_on=date(this_year,12,31),fee=250,soccs_percent=40,ituh_percent=30,css_percent=30)
        budget = Budget(name='First semester activities',kind='Semester',starts_on=date(this_year,1,1),ends_on=date(this_year,12,31),active=True)
        categories = [BudgetCategory(budget=budget,name=name,allocated=amount) for name,amount in [('Student events',10000),('Printing & materials',2000),('Equipment',5000)]]
        db.session.add_all([year,budget,*categories])
        members = []
        for i, name in enumerate(['Alex Rivera','Jamie Santos','Taylor Cruz','Morgan Reyes','Casey Garcia','Sam Mendoza','Jordan Flores','Avery Ramos','Riley Torres','Drew Aquino','Sky Navarro','Robin Castillo']):
            m=Member(student_number=f'DEMO-{i+1:04}',full_name=name,program='IT' if i%2 else 'CS',year_level=i%4+1,section='A' if i%2 else 'B',active=True,contact='')
            db.session.add(m)
            members.append(m)
        db.session.flush()
        for i,m in enumerate(members[:9]):
            submit_transaction(users['Treasurer'] if i<7 else users['Coordinator'],kind='Payment',amount=250,
                occurred_on=today()-timedelta(days=i*3),description='Annual membership fee',method='Cash',reference='',
                submission_key=secrets.token_hex(24),member_id=m.id,academic_year_id=year.id)
        for offset in range(6):
            day=today()-timedelta(days=offset*28)
            submit_transaction(users['Treasurer'],kind='Income',amount=Decimal(2600+offset*350),occurred_on=day,
                description='Water refilling station collections',method='Cash',reference='',submission_key=secrets.token_hex(24))
        for i, (amount,cat) in enumerate([(4200,categories[0]),(1650,categories[1]),(950,categories[2])]):
            submit_transaction(users['Treasurer'],kind='Expense',amount=amount,occurred_on=today()-timedelta(days=i*25),
                description=['Student assembly supplies','Membership forms and printing','Equipment maintenance'][i],method='Cash',reference=f'DEMO-EXP-{i+1}',category_id=cat.id,submission_key=secrets.token_hex(24))
        db.session.commit()
print('Sample preview: http://127.0.0.1:5001 | treasurer / Preview-only-2026!', flush=True)
serve(app,host='127.0.0.1',port=5001)
