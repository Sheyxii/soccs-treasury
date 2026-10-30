"""Business invariants and full officer HTTP workflows against migrated databases."""
import json
import re
import secrets
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import AcademicYear, Member, User, Transaction, Payment, Income, Expense, Receipt, Budget, BudgetCategory, AuditLog
from app.finance.services import submit_transaction, decide_transaction, totals, today, BusinessError
from app.backups import create_backup, restore_backup, files, load_backup
from tests.test_foundation import login, csrf
from tests.conftest import PASSWORD


@pytest.fixture
def records(app, tmp_path):
    app.config['BACKUP_DIRECTORY'] = str(tmp_path / 'backups')
    with app.app_context():
        year = AcademicYear(name='2026-2027', starts_on=date(2026, 1, 1), ends_on=date(2027, 12, 31), fee=250, soccs_percent=40, ituh_percent=30, css_percent=30)
        member = Member(student_number='2026-0001', full_name='Sample Student', program='IT', year_level=1, section='A', contact='', active=True)
        budget = Budget(name='Student Assembly', kind='Event', starts_on=date(2026,1,1), ends_on=date(2027,12,31), active=True)
        category = BudgetCategory(budget=budget, name='Printing', allocated=1000)
        db.session.add_all([year,member,budget,category])
        db.session.commit()
        return dict(member_id=member.id, academic_year_id=year.id, category_id=category.id)


def officer(name):
    return db.session.scalar(db.select(User).where(User.username == name))


def submit(role='treasurer', kind='Payment', **kwargs):
    values = dict(kind=kind, amount=250, occurred_on=date(2026, 10, 1), description='Annual membership fee', method='Cash', reference='', submission_key=secrets.token_hex(24))
    values.update(kwargs)
    return submit_transaction(officer(role), **values)


def post(client, path, data, token_path='/'):
    return client.post(path, data={**data, 'csrf_token': csrf(client, token_path)}, follow_redirects=True)


@pytest.mark.parametrize('program', ['IT','CS'])
def test_confirmed_three_way_split_for_every_student(app, records, program):
    with app.app_context():
        db.session.get(Member, records['member_id']).program = program
        tx = submit(**records)
        db.session.commit()
        assert tx.status == 'Approved'
        assert tx.payment.receipt.number == 'RCT-000001'
        inc = db.session.scalar(db.select(Income))
        assert (inc.amount,inc.soccs_share,inc.ituh_share,inc.css_share) == (250,100,75,75)
        assert totals()['balance'] == 100
        assert db.session.scalar(db.select(db.func.count(AuditLog.id)).where(AuditLog.record == tx.number)) == 2


def test_pending_does_not_post_reject_releases_reservation(app, records):
    with app.app_context():
        tx = submit('coordinator', **records)
        db.session.commit()
        assert tx.status == 'Pending' and totals()['gross'] == 0
        with pytest.raises(BusinessError, match='already has'):
            submit(**records)
        db.session.rollback()
        with pytest.raises(BusinessError, match='reason'):
            decide_transaction(tx.id, officer('treasurer'), 'reject', '')
        decide_transaction(tx.id, officer('treasurer'), 'reject', 'Incorrect evidence')
        db.session.commit()
        assert not tx.payment
        replacement = submit(**records)
        db.session.commit()
        assert replacement.payment
        with pytest.raises(BusinessError, match='already been decided'):
            decide_transaction(tx.id, officer('treasurer'), 'approve', '')


def test_approve_is_atomic_and_cannot_repeat(app, records):
    with app.app_context():
        tx = submit('coordinator', **records)
        db.session.commit()
        decide_transaction(tx.id, officer('treasurer'), 'approve', 'Cash received')
        db.session.rollback()  # Simulate a failed outer transaction after all child rows were flushed.
        assert db.session.get(Transaction,tx.id).status == 'Pending'
        for model in (Payment,Income,Receipt):
            assert db.session.scalar(db.select(db.func.count(model.id))) == 0
        decide_transaction(tx.id, officer('treasurer'), 'approve', 'Cash received')
        db.session.commit()
        with pytest.raises(BusinessError):
            decide_transaction(tx.id, officer('treasurer'), 'approve', 'Repeat')
        assert db.session.scalar(db.select(db.func.count(Payment.id))) == 1


def test_overspend_held_until_explicit_reason_and_rechecked(app, records):
    with app.app_context():
        tx = submit(kind='Expense',amount=1100,reference='EXP-001',category_id=records['category_id'])
        db.session.commit()
        assert tx.status == 'Pending' and tx.overspend
        assert db.session.get(BudgetCategory,records['category_id']).spent == 0
        with pytest.raises(BusinessError,match='Explain'):
            decide_transaction(tx.id,officer('treasurer'),'approve','')
        db.session.rollback()
        decide_transaction(tx.id,officer('treasurer'),'approve','Approved event printing overrun')
        db.session.commit()
        assert db.session.get(BudgetCategory,records['category_id']).remaining == -100
        assert totals()['expenses'] == 1100


def test_concurrent_pending_expenses_recheck_budget(app, records):
    with app.app_context():
        first=submit('coordinator',kind='Expense',amount=700,reference='EXP-A',category_id=records['category_id'])
        second=submit('coordinator',kind='Expense',amount=700,reference='EXP-B',category_id=records['category_id'])
        db.session.commit()
        decide_transaction(first.id,officer('treasurer'),'approve','')
        db.session.commit()
        with pytest.raises(BusinessError,match='Explain'):
            decide_transaction(second.id,officer('treasurer'),'approve','')
        db.session.rollback()
        assert db.session.get(BudgetCategory,records['category_id']).spent == 700
        decide_transaction(second.id,officer('treasurer'),'approve','Additional allocation authorized')
        db.session.commit()
        assert second.overspend and second.reviewer_id


@pytest.mark.parametrize('changes', [{'amount':249},{'amount':0},{'amount':-1},{'amount':'250.001'}, {'occurred_on':date(2025,1,1)}, {'occurred_on':today()+timedelta(days=1)}, {'method':'GCash','reference':''}, {'method':'GCash','reference':'abc'}, {'description':'   '}])
def test_invalid_transactions_do_not_write(app,records,changes):
    with app.app_context():
        with pytest.raises(BusinessError):
            submit(**records,**changes)
        db.session.rollback()
        assert totals()['gross']==0


def test_unique_gcash_reference_across_income_and_membership(app,records):
    with app.app_context():
        submit(method='GCash',reference='1234567890123',**records)
        db.session.commit()
        with pytest.raises(IntegrityError):
            submit(kind='Income',amount=500,method='GCash',reference='1234567890123')
        db.session.rollback()
        assert totals()['gross']==250


@pytest.mark.parametrize('role,allowed',[
 ('treasurer',{'/members','/transactions','/budgets','/reports','/settings','/backups'}),
 ('coordinator',{'/members','/transactions'}),
 ('auditor',{'/members','/transactions','/budgets','/reports'}),
 ('president',{'/reports'}),('adviser',{'/reports'})])
def test_live_role_pages(client,records,role,allowed):
    login(client,role)
    for path in ['/members','/transactions','/budgets','/reports','/settings','/backups']:
        response=client.get(path)
        assert response.status_code==(200 if path in allowed else 403), (role,path,response.text[:1000])
    assert client.get('/').status_code==200


def test_http_collection_review_receipt_and_report(app,client,records):
    login(client,'coordinator')
    page=client.get('/transactions/new/Payment')
    key=re.search(r'name="submission_key"[^>]*value="([^"]+)"',page.text).group(1)
    data=dict(records,amount='250',occurred_on='2026-10-01',method='GCash',reference='9876543210001',description='Membership collection',submission_key=key)
    response=post(client,'/transactions/new/Payment',data)
    assert response.status_code==200 and 'Awaiting Treasurer review' in response.text
    with app.app_context():
        tx_id=db.session.scalar(db.select(Transaction.id))
        assert tx_id and totals()['gross']==0
    post(client,'/auth/logout',{})
    login(client,'treasurer')
    result=post(client,f'/transactions/{tx_id}/decide',dict(decision='approve',remarks='GCash verified manually'))
    assert 'View receipt' in result.text
    assert client.get('/receipts/1').status_code==200
    report=client.get('/reports?start=2026-10-01&end=2026-10-31')
    assert report.status_code==200 and '250.00' in report.text
    exported=client.get('/reports/export?start=2026-10-01&end=2026-10-31')
    assert exported.status_code==200 and '100.00,75.00,75.00' in exported.text
    result=post(client,f'/transactions/{tx_id}/verify',{})
    assert 'Verified by' in result.text


def test_members_budget_policy_forms(client,records):
    login(client)
    response=post(client,'/members/new',dict(student_number='2026-9999',full_name='Another Student',program='CS',year_level=2,section='B',contact='',active='y'),'/members/new')
    assert 'Another Student' in response.text
    response=post(client,'/budgets/new',dict(name='Semester operations',kind='Semester',starts_on='2026-01-01',ends_on='2026-12-31'),'/budgets/new')
    assert 'Category allocations' in response.text
    response=post(client,'/budgets/2/categories',dict(name='Equipment',allocated=5000))
    assert 'Equipment' in response.text
    response=post(client,'/settings',dict(name='2028-2029',fee=250,starts_on='2028-08-01',ends_on='2029-07-31',soccs_percent=40,ituh_percent=30,css_percent=30),'/settings')
    assert 'Academic year and fee policy saved' in response.text


def test_decimal_nonfinite_form_rejected(client,records):
    login(client)
    page=client.get('/transactions/new/Income')
    key=re.search(r'name="submission_key"[^>]*value="([^"]+)"',page.text).group(1)
    response=post(client,'/transactions/new/Income',dict(amount='NaN',occurred_on='2026-10-01',method='Cash',description='Water collection',submission_key=key))
    assert response.status_code==200 and 'finite amount' in response.text


def test_coordinator_cannot_read_another_request(app,client,records):
    with app.app_context():
        tx=submit(**records)
        db.session.commit()
        tx_id=tx.id
    login(client,'coordinator')
    assert client.get(f'/transactions/{tx_id}').status_code==403
    assert client.get('/receipts/1').status_code==403
    assert client.post(f'/transactions/{tx_id}/decide',data={'csrf_token':csrf(client,'/'),'decision':'reject','remarks':'bad'}).status_code==403


def test_backups_roundtrip_integrity_retention(app,records):
    with app.app_context():
        submit(**records)
        db.session.commit()
        before=officer('treasurer').session_token
        backup=create_backup('test')
        submit(kind='Income',amount=900)
        db.session.commit()
        restore_backup(backup,'test')
        assert totals()['gross']==250
        assert officer('treasurer').session_token!=before
        assert db.session.scalar(db.select(Receipt)).payment.transaction.member_name=='Sample Student'
        for _ in range(5): create_backup('test')
        assert len(files())==4
        bad=files()[0]
        envelope=json.loads(bad.read_text())
        envelope['payload']=envelope['payload'].replace('Sample Student','Tampered Name')
        bad.write_text(json.dumps(envelope))
        with pytest.raises(ValueError,match='integrity'):
            load_backup(bad)


def test_backup_restore_ui_requires_password(client,records):
    login(client)
    post(client,'/backups',{})
    response=client.get('/backups')
    target=re.search(r'action="(/backups/[^\"]+/restore)"',response.text).group(1)
    denied=post(client,target,dict(confirmation='RESTORE',password='wrong'))
    assert 'current password' in denied.text
    restored=post(client,target,dict(confirmation='RESTORE',password=PASSWORD))
    assert 'Backup restored' in restored.text
    assert client.get('/').status_code==302


@pytest.mark.parametrize('role', ['president', 'adviser'])
def test_oversight_dashboard_excludes_individual_member_records(app, client, records, role):
    with app.app_context():
        submit(**records)
        db.session.commit()
    login(client, role)
    response = client.get('/')
    assert response.status_code == 200
    assert 'Sample Student' not in response.text
    assert 'This month' in response.text
    assert '250.00' in response.text


def test_restore_constraint_failure_preserves_current_records(app, records):
    from app.backups import signature
    with app.app_context():
        submit(**records)
        db.session.commit()
        path = create_backup('test')
        envelope = json.loads(path.read_text())
        payload = json.loads(envelope['payload'])
        payload['tables']['payments'][0]['member_id'] = 999999
        envelope['payload'] = json.dumps(payload)
        envelope['signature'] = signature(envelope['payload'])
        path.write_text(json.dumps(envelope))
        with pytest.raises(IntegrityError):
            restore_backup(path, 'test')
        assert totals()['gross'] == 250
        assert db.session.scalar(db.select(Receipt)).payment.transaction.member_name == 'Sample Student'


def test_automatic_backup_unwritable_directory_does_not_break_pages(app, monkeypatch):
    from app import backups
    def unavailable():
        raise PermissionError('Simulated unavailable backup folder')
    with app.app_context():
        app.config.update(TESTING=False, AUTO_BACKUP=True)
        monkeypatch.setattr(backups, 'files', unavailable)
        backups.automatic_backup()
        assert app.extensions['backup_error'] is True


def test_search_suggestions_match_words_and_respect_roles(app, client, records):
    with app.app_context():
        submit(**records)
        db.session.commit()
    login(client, 'treasurer')
    data = client.get('/search/suggest?q=student sample').get_json()
    assert [m['label'] for m in data['members']] == ['Sample Student']
    assert data['transactions'] and data['transactions'][0]['status'] == 'Approved'
    assert client.get('/search/suggest?q=TXN-1').get_json()['transactions'][0]['label'].startswith('TXN-000001')
    assert client.get('/search/suggest?q=s').get_json()['members'] == []
    assert client.get('/search?q=sample student').status_code == 200
    post(client, '/auth/logout', {})
    login(client, 'coordinator')
    data = client.get('/search/suggest?q=sample').get_json()
    assert data['members'] and data['transactions'] == []
    post(client, '/auth/logout', {})
    login(client, 'president')
    assert client.get('/search/suggest?q=sample').status_code == 403


def coordinator_request(client, kind, data):
    page = client.get(f'/transactions/new/{kind}')
    key = re.search(r'name="submission_key"[^>]*value="([^"]+)"', page.text).group(1)
    response = post(client, f'/transactions/new/{kind}', dict(data, submission_key=key))
    assert 'Awaiting Treasurer review' in response.text or 'Over budget' in response.text, response.text[:2000]
    return int(re.search(r'<h1>TXN-0*(\d+)</h1>', response.text).group(1))


def decide_from_page(client, tx_id, decision, remarks=''):
    page = client.get(f'/transactions/{tx_id}')
    assert 'Confirm decision' in page.text or 'Approve' in page.text
    return post(client, f'/transactions/{tx_id}/decide', dict(decision=decision, remarks=remarks), f'/transactions/{tx_id}')


def test_treasurer_processes_every_kind_of_coordinator_request(app, client, records):
    login(client, 'coordinator')
    expense = coordinator_request(client, 'Expense', dict(category_id=records['category_id'], amount='300', occurred_on='2026-10-01', method='Cash', reference='OR-1', description='Printing handouts'))
    over = coordinator_request(client, 'Expense', dict(category_id=records['category_id'], amount='5000', occurred_on='2026-10-01', method='Cash', reference='OR-2', description='Tarpaulin printing'))
    payment = coordinator_request(client, 'Payment', dict(records, amount='250', occurred_on='2026-10-01', method='Cash', reference='', description='Annual membership fee'))
    post(client, '/auth/logout', {})
    login(client, 'treasurer')
    pending = client.get('/transactions?status=Pending').text
    assert all(f'TXN-{n:06d}' in pending for n in (expense, over, payment))
    assert 'Decision saved' in decide_from_page(client, expense, 'approve').text
    assert 'Explain why this over-budget expense is authorized' in decide_from_page(client, over, 'approve').text
    assert 'Decision saved' in decide_from_page(client, over, 'approve', 'Approved by officers meeting').text
    assert 'A rejection reason is required' in decide_from_page(client, payment, 'reject').text
    assert 'Decision saved' in decide_from_page(client, payment, 'reject', 'Duplicate entry').text
    with app.app_context():
        status = {t.id: t.status for t in db.session.scalars(db.select(Transaction))}
        assert (status[expense], status[over], status[payment]) == ('Approved', 'Approved', 'Rejected')


@pytest.mark.parametrize('number,ok', [('2026-0002', True), (' 2026-0002 ', True), ('2026-002', False), ('20260002', False),
                                       ('2026-00A2', False), ('AB26-0002', False), ('2026-00002', False), ('2026-0002x', False)])
def test_student_number_format(client, records, number, ok):
    login(client)
    response = post(client, '/members/new', dict(student_number=number, full_name='Format Check', program='IT', year_level=1, section='A', contact='', active='y'), '/members/new')
    assert ('Member record saved' in response.text) == ok
    if not ok:
        assert 'Use the format 1234-5678' in response.text


def test_delete_only_inactive_members_without_records(app, client, records):
    with app.app_context():
        spare = Member(student_number='2026-0099', full_name='Spare Student', program='CS', year_level=1, section='B', contact='', active=True)
        db.session.add(spare)
        submit(**records)
        db.session.commit()
        spare_id, paid_id = spare.id, records['member_id']
    login(client)
    post(client, f'/members/{spare_id}/delete', {}, f'/members/{spare_id}')
    with app.app_context():
        assert db.session.get(Member, spare_id) is not None  # still active: refused
        db.session.get(Member, spare_id).active = False
        db.session.get(Member, paid_id).active = False
        db.session.commit()
    page = client.get(f'/members/{paid_id}').text
    assert 'has payment records' in page and 'Delete member</button>' not in page
    assert 'Delete member</button>' in client.get(f'/members/{spare_id}').text
    response = post(client, f'/members/{paid_id}/delete', {}, f'/members/{paid_id}')
    assert 'cannot be deleted' in response.text
    response = post(client, f'/members/{spare_id}/delete', {}, f'/members/{spare_id}')
    assert 'Spare Student was deleted' in response.text
    with app.app_context():
        assert db.session.get(Member, spare_id) is None and db.session.get(Member, paid_id) is not None
        assert db.session.scalar(db.select(AuditLog).where(AuditLog.action == 'member.deleted')).remarks == 'Spare Student'
    post(client, '/auth/logout', {})
    login(client, 'auditor')
    assert client.post(f'/members/{paid_id}/delete', data={'csrf_token': csrf(client, '/')}).status_code == 403


def test_transactions_list_shows_ten_latest_first(app, client, records):
    with app.app_context():
        for day in range(1, 13):  # entered oldest-date-last on purpose
            submit(kind='Income', amount=10, occurred_on=date(2026, 10, 13 - day), description=f'Water day {13 - day}')
        db.session.commit()
    login(client)
    first = client.get('/transactions').text
    numbers = re.findall(r'class="record-link" href="/transactions/\d+">(TXN-\d+)</a>', first)
    assert len(numbers) == 10
    dates = re.findall(r'<td class="text-nowrap">(\d{2} \w{3} \d{4})</td>', first)
    assert dates[0] == '12 Oct 2026' and dates[-1] == '03 Oct 2026'
    assert 'Showing 1–10 of 12' in first
    second = client.get('/transactions?page=2').text
    assert len(re.findall(r'class="record-link" href="/transactions/\d+">', second)) == 2 and 'Showing 11–12 of 12' in second


def test_login_pauses_after_repeated_wrong_passwords(app, client):
    for _ in range(5):
        client.post('/auth/login', data={'csrf_token': csrf(client, '/auth/login'), 'username': 'auditor', 'password': 'wrong-password-x'})
    page = client.post('/auth/login', data={'csrf_token': csrf(client, '/auth/login'), 'username': 'auditor', 'password': PASSWORD}, follow_redirects=True)
    assert 'Too many failed sign-in attempts' in page.text
    login(client, 'treasurer')  # other accounts are unaffected
    assert client.get('/').status_code == 200


def test_close_and_reopen_budget(app, client, records):
    login(client)
    with app.app_context():
        budget_id = db.session.get(BudgetCategory, records['category_id']).budget_id
    page = post(client, f'/budgets/{budget_id}/status', {}, f'/budgets/{budget_id}')
    assert 'was closed' in page.text
    form = client.get('/transactions/new/Expense').text
    assert 'Printing' not in form  # closed budgets are not offered for new expenses
    assert 'was reopened' in post(client, f'/budgets/{budget_id}/status', {}, f'/budgets/{budget_id}').text


def test_unpaid_filter_lists_only_active_members(app, client, records):
    with app.app_context():
        db.session.add(Member(student_number='2026-0050', full_name='Gone Student', program='IT', year_level=2, section='C', contact='', active=False))
        db.session.commit()
    login(client)
    page = client.get('/members?status=unpaid').text
    assert 'Sample Student' in page and 'Gone Student' not in page


def test_health_error_pages_and_security_headers(app, client, records):
    assert client.get('/health').get_json() == {'status': 'ok'}
    login(client)
    missing = client.get('/members/99999')
    assert missing.status_code == 404 and 'Page not found' in missing.text and 'Go to overview' in missing.text
    assert client.get('/transactions/1/decide').status_code == 405
    headers = client.get('/').headers
    assert "script-src 'self'" in headers['Content-Security-Policy'] and headers['X-Frame-Options'] == 'DENY'


def test_audit_search_survives_paging(app, client):
    with app.app_context():
        for n in range(30):
            db.session.add(AuditLog(actor='treasurer', action='member.updated', record=f'member:x{n}', remarks=''))
        db.session.commit()
    login(client)
    first = client.get('/audit?q=member.updated').text
    assert 'page=2' in first and 'q=member.updated' in first.split('page=2')[0][-200:] + first.split('page=2')[1][:200]


@pytest.mark.parametrize('role', ['treasurer', 'coordinator', 'auditor', 'president', 'adviser'])
def test_every_page_renders_for_every_role(app, client, records, role):
    """Crawl every link reachable from the overview; nothing may crash."""
    with app.app_context():
        submit(**records)
        submit(kind='Expense', amount=100, reference='OR-9', category_id=records['category_id'], description='Ink')
        db.session.commit()
    login(client, role)
    seen, queue = set(), ['/', '/search?q=sample', '/me', '/reports', '/transactions/new/Payment', '/transactions/new/Expense',
                          '/transactions/new/Income', '/members/new', '/budgets/new', '/receipts/1', '/transactions/1']
    while queue and len(seen) < 80:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        response = client.get(path)
        assert response.status_code in (200, 302, 403, 404), (role, path, response.status_code)
        if response.status_code == 200 and response.mimetype == 'text/html':
            for link in re.findall(r'href="(/[^"#]*)"', response.text):
                link = link.replace('&amp;', '&')
                if not link.startswith(('/static', '/auth/logout', '/backups/')) and 'export' not in link:
                    queue.append(link)
    assert len(seen) > 5


@pytest.mark.parametrize('amount,words', [
    ('250', 'Two hundred fifty pesos only'), ('1', 'One peso only'), ('0.75', 'Zero pesos and seventy-five centavos only'),
    ('1250.50', 'One thousand two hundred fifty pesos and fifty centavos only'),
    ('2000000', 'Two million pesos only'), ('115', 'One hundred fifteen pesos only')])
def test_amount_in_words(amount, words):
    from app.finance.words import peso_words
    assert peso_words(Decimal(amount)) == words


def test_official_receipt_content(app, client, records):
    with app.app_context():
        submit(**records)
        db.session.commit()
    login(client)
    page = client.get('/receipts/1').text
    for text in ('Official receipt', 'RCT-000001', 'Sample Student', 'Two hundred fifty pesos only', '₱100.00', '₱75.00', 'Received by', 'TXN-000001'):
        assert text in page, text


def test_receipt_pdf_download(app, client, records):
    with app.app_context():
        submit(**records)
        db.session.commit()
    login(client)
    response = client.get('/receipts/1/pdf')
    assert response.status_code == 200 and response.mimetype == 'application/pdf'
    assert response.data.startswith(b'%PDF') and 'RCT-000001.pdf' in response.headers['Content-Disposition']
    post(client, '/auth/logout', {})
    login(client, 'coordinator')
    assert client.get('/receipts/1/pdf').status_code == 403
