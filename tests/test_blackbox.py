"""Acceptance tests through HTTP forms, pages, downloads and public responses.

Only the shared fixture provisions the disposable database and officer accounts.
These scenarios do not query models or call business services to arrange or verify
financial records. CSRF tokens and record identifiers come from rendered pages.
"""
import csv
import io
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import pytest

from tests.conftest import PASSWORD

pytestmark = pytest.mark.blackbox
ROLES = ('treasurer', 'coordinator', 'auditor', 'president', 'adviser')


class FormPage(HTMLParser):
    def __init__(self, response):
        super().__init__()
        assert response.status_code == 200, response.text
        self.hidden = {}
        self.options = {}
        self.links = []
        self.select = None
        self.feed(response.text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden':
            self.hidden[attrs['name']] = attrs.get('value', '')
        if tag == 'select':
            self.select = attrs.get('name')
        if tag == 'option' and self.select:
            self.options.setdefault(self.select, []).append(attrs.get('value'))
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag == 'select':
            self.select = None


def send(client, path, data=None, *, page=None, follow=True):
    fields = FormPage(client.get(page or path)).hidden
    return client.post(path, data={**fields, **(data or {})}, follow_redirects=follow)


def sign_in(client, role, password=PASSWORD):
    response = send(client, '/auth/login', {'username': role, 'password': password}, follow=False)
    assert response.status_code == 302, response.text
    return client


def created_path(response, prefix):
    assert response.status_code == 302, response.text
    assert re.fullmatch(prefix + r'/\d+', response.location), response.location
    return response.location


@pytest.fixture
def office(app, tmp_path):
    app.config['BACKUP_DIRECTORY'] = str(tmp_path / 'blackbox-backups')
    clients = {role: sign_in(app.test_client(), role) for role in ROLES}
    treasurer = clients['treasurer']
    day = datetime.now(timezone(timedelta(hours=8))).date()
    start, end = f'{day.year}-01-01', f'{day.year + 1}-12-31'
    response = send(treasurer, '/settings', dict(
        name=f'{day.year}-{day.year + 1}', starts_on=start, ends_on=end,
        fee='250', soccs_percent='40', ituh_percent='30', css_percent='30'))
    assert 'Academic year and fee policy saved.' in response.text
    member_data = dict(student_number='2026-9001', full_name='Blackbox Student',
                       program='IT', year_level='1', section='A', contact='', active='y')
    member = created_path(send(treasurer, '/members/new', member_data, follow=False), '/members')
    budget = created_path(send(treasurer, '/budgets/new', dict(
        name='Blackbox Event', kind='Event', starts_on=start, ends_on=end), follow=False), '/budgets')
    assert 'Budget category saved.' in send(treasurer, budget + '/categories',
        dict(name='Supplies', allocated='1000'), page=budget).text
    payment_page = FormPage(treasurer.get('/transactions/new/Payment'))
    expense_page = FormPage(treasurer.get('/transactions/new/Expense'))
    return dict(clients=clients, day=day, start=start, end=end, member=member,
                member_data=member_data, budget=budget,
                payment=dict(member_id=member.rsplit('/', 1)[1],
                             academic_year_id=payment_page.options['academic_year_id'][1],
                             amount='250', occurred_on=day.isoformat(), method='Cash',
                             reference='', description='Annual membership fee'),
                category=expense_page.options['category_id'][1])


def payment(office, role='treasurer', **changes):
    return send(office['clients'][role], '/transactions/new/Payment',
                {**office['payment'], **changes}, follow=False)


def report(office, **filters):
    response = office['clients']['treasurer'].get('/reports/export', query_string={
        'start': office['start'], 'end': office['end'], **filters})
    assert response.status_code == 200, response.text
    assert response.mimetype == 'text/csv'
    return list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))))


def total(office, name, **filters):
    return next(row[1] for row in report(office, **filters) if row and row[0] == name)


def decide(office, path, decision, remarks=''):
    return send(office['clients']['treasurer'], path + '/decide',
                dict(decision=decision, remarks=remarks), page=path)


@pytest.mark.parametrize('role', ROLES)
def test_real_routes_enforce_each_role(office, role):
    client = office['clients'][role]
    tx = created_path(payment(office, 'coordinator'), '/transactions')
    pages = {
        '/': ROLES, '/users/me': ROLES,
        '/members': ('treasurer', 'coordinator', 'auditor'),
        '/members/new': ('treasurer', 'coordinator'),
        '/transactions': ('treasurer', 'coordinator', 'auditor'),
        tx: ('treasurer', 'coordinator', 'auditor'),
        '/transactions/new/Payment': ('treasurer', 'coordinator'),
        '/transactions/new/Expense': ('treasurer', 'coordinator'),
        '/transactions/new/Income': ('treasurer',),
        '/budgets': ('treasurer', 'auditor'), '/budgets/new': ('treasurer',),
        '/settings': ('treasurer',), '/backups': ('treasurer',),
        '/reports': ('treasurer', 'auditor', 'president', 'adviser'),
        '/reports/export': ('treasurer', 'auditor', 'president', 'adviser'),
        '/audit': ('treasurer', 'auditor'),
        '/search/suggest?q=Blackbox': ('treasurer', 'coordinator', 'auditor'),
    }
    for path, allowed in pages.items():
        assert client.get(path).status_code == (200 if role in allowed else 403), (role, path)
    if role != 'treasurer':
        response = send(client, tx + '/decide', dict(decision='approve'), page='/users/me')
        assert response.status_code == 403
        assert send(client, '/backups', page='/users/me').status_code == 403
        assert send(client, office['budget'] + '/status', page='/users/me').status_code == 403
        assert total(office, 'gross') == '0.00'


def test_pending_payment_to_paid_receipt_and_verification(office):
    treasurer, coordinator, auditor = [office['clients'][r] for r in ROLES[:3]]
    tx = created_path(payment(office, 'coordinator'), '/transactions')
    assert 'Pending' in coordinator.get(tx).text
    assert total(office, 'gross') == '0.00'
    assert 'Blackbox Student' in treasurer.get('/members?status=unpaid').text
    processed = payment(office, method='GCash', reference='1234567890123', description='Received payment')
    assert processed.location == tx
    page = treasurer.get(tx)
    assert 'Approved' in page.text and 'Test Coordinator' in page.text
    receipt = next(link for link in FormPage(page).links if re.fullmatch(r'/receipts/\d+', link))
    assert 'Blackbox Student' in treasurer.get(receipt).text
    with treasurer.get(receipt + '/pdf') as pdf:
        assert pdf.status_code == 200 and pdf.mimetype == 'application/pdf'
        assert pdf.data.startswith(b'%PDF-')
    assert total(office, 'gross') == '250.00'
    assert total(office, 'soccs') == '100.00'
    assert total(office, 'ituh') == total(office, 'css') == '75.00'
    assert 'Blackbox Student' in treasurer.get('/members?status=paid').text
    assert 'Blackbox Student' not in treasurer.get('/members?status=unpaid').text
    verified = send(auditor, tx + '/verify', page=tx)
    assert 'Verified by Test Auditor' in verified.text
    assert 'already has' in payment(office).text
    assert total(office, 'gross') == '250.00'


def test_reject_correct_and_resubmit(office):
    tx = created_path(payment(office, 'coordinator', method='GCash', reference='1234567890123'), '/transactions')
    assert 'rejection reason is required' in decide(office, tx, 'reject').text
    assert 'Rejected' in decide(office, tx, 'reject', 'Payment evidence was incorrect').text
    assert total(office, 'gross') == '0.00'
    new_tx = created_path(payment(office, 'coordinator', method='GCash', reference='1234567890123'), '/transactions')
    assert new_tx != tx
    assert 'Approved' in decide(office, new_tx, 'approve', 'Evidence checked').text
    assert 'already been decided' in decide(office, tx, 'approve').text
    assert total(office, 'gross') == '250.00'


@pytest.mark.parametrize('changes', [
    {'amount': '0'}, {'amount': '-1'}, {'amount': '249'}, {'amount': '250.001'},
    {'amount': 'NaN'}, {'amount': 'Infinity'}, {'amount': 'not-money'},
    {'method': 'GCash', 'reference': ''}, {'method': 'GCash', 'reference': '123'},
    {'member_id': '999999'}, {'academic_year_id': '999999'},
    {'description': '   '}, {'occurred_on': 'not-a-date'},
])
def test_invalid_payment_does_not_change_pending_or_accounts(office, changes):
    tx = created_path(payment(office, 'coordinator'), '/transactions')
    rejected = payment(office, **changes)
    assert rejected.status_code == 200
    assert 'Pending' in office['clients']['treasurer'].get(tx).text
    assert total(office, 'gross') == '0.00'
    assert payment(office).location == tx
    assert total(office, 'gross') == '250.00'


def test_duplicate_reference_and_double_submit_are_atomic(office):
    treasurer = office['clients']['treasurer']
    tx = created_path(payment(office, 'coordinator'), '/transactions')
    data = dict(amount='500', occurred_on=office['day'].isoformat(), method='GCash',
                reference='1234567890123', description='Water collection')
    path = '/transactions/new/Income'
    submitted = {**FormPage(treasurer.get(path)).hidden, **data}
    assert treasurer.post(path, data=submitted).status_code == 302
    assert 'already submitted' in treasurer.post(path, data=submitted).text
    assert payment(office, method='GCash', reference='1234567890123').status_code == 200
    assert 'Pending' in treasurer.get(tx).text
    assert total(office, 'gross') == '500.00'
    assert payment(office).location == tx
    assert total(office, 'gross') == '750.00'


def test_budget_overspending_reallocation_and_closed_budget(office):
    treasurer = office['clients']['treasurer']
    expense = dict(amount='1100', occurred_on=office['day'].isoformat(), method='Cash',
                   reference='OR-100', description='Event supplies', category_id=office['category'])
    tx = created_path(send(office['clients']['coordinator'], '/transactions/new/Expense', expense, follow=False), '/transactions')
    assert total(office, 'expenses') == '0.00'
    assert 'Explain why' in decide(office, tx, 'approve').text
    assert 'Approved' in decide(office, tx, 'approve', 'Additional allocation authorized').text
    assert total(office, 'expenses') == '1100.00'
    category = office['budget'] + '/categories/' + office['category']
    assert 'cannot be reduced below posted spending' in send(treasurer, category,
        dict(name='Supplies', allocated='100')).text
    send(treasurer, office['budget'] + '/status', page=office['budget'])
    assert send(treasurer, '/transactions/new/Expense', expense, follow=False).status_code == 200
    assert total(office, 'expenses') == '1100.00'
    send(treasurer, office['budget'] + '/status', page=office['budget'])
    assert send(treasurer, '/transactions/new/Expense', expense, follow=False).status_code == 302


@pytest.mark.parametrize('path', ['/members/new', '/settings', '/budgets/new',
                                 '/transactions/new/Payment', '/backups', '/auth/logout'])
def test_mutations_require_csrf(office, path):
    treasurer = office['clients']['treasurer']
    assert treasurer.post(path, data=office['payment']).status_code == 400
    assert treasurer.get('/').status_code == 200
    assert total(office, 'gross') == '0.00'


def test_search_escaping_csv_and_invalid_report_filters(office):
    treasurer = office['clients']['treasurer']
    unsafe_name = '<script>alert(1)</script>'
    response = send(treasurer, office['member'] + '/edit',
                    {**office['member_data'], 'full_name': unsafe_name})
    assert unsafe_name not in response.text and '&lt;script&gt;' in response.text
    tx = created_path(payment(office, description='=SUM(1,2)'), '/transactions')
    rows = report(office)
    row = next(row for row in rows if row and row[0].startswith('TXN-'))
    assert row[3] == "'=SUM(1,2)"
    for query in ["' OR 1=1 --", '%', '_', '<script>']:
        assert treasurer.get('/search', query_string={'q': query}).status_code == 200
        assert treasurer.get('/search/suggest', query_string={'q': query}).status_code == 200
    for filters in [{'start': 'bad'}, {'start': '2026-12-31', 'end': '2026-01-01'},
                    {'budget': '999999'}, {'year': '999999'}]:
        for path in ('/reports', '/reports/export'):
            assert treasurer.get(path, query_string=filters).status_code in (400, 404)
    assert 'Approved' in treasurer.get(tx).text


def test_backup_download_import_restore_and_session_revocation(office):
    treasurer = office['clients']['treasurer']
    page = send(treasurer, '/backups')
    download = next(link for link in FormPage(page).links if link.endswith('/download'))
    with treasurer.get(download) as response:
        assert response.status_code == 200
        backup = response.data
    assert 'Backup imported and verified' in send(treasurer, '/backups/import',
        {'backup': (io.BytesIO(backup), 'saved.json')}, page='/backups').text
    tx = created_path(payment(office), '/transactions')
    restore = download.removesuffix('/download') + '/restore'
    wrong = send(treasurer, restore, dict(confirmation='RESTORE', password='wrong'), page='/backups')
    assert 'current password' in wrong.text and total(office, 'gross') == '250.00'
    restored = send(treasurer, restore, dict(confirmation='RESTORE', password=PASSWORD), page='/backups')
    assert 'Backup restored.' in restored.text
    for client in office['clients'].values():
        assert client.get('/').status_code == 302
    sign_in(treasurer, 'treasurer')
    assert total(office, 'gross') == '0.00'
    assert treasurer.get(tx).status_code == 404
    assert 'Blackbox Student' in treasurer.get('/members').text


@pytest.mark.parametrize('payload', [b'not json', b'{}', b'[]', b'\xff\xfe',
                                    b'{"payload":"{}","signature":"invalid"}'])
def test_invalid_backup_upload_preserves_records(office, payload):
    treasurer = office['clients']['treasurer']
    created_path(payment(office), '/transactions')
    response = send(treasurer, '/backups/import',
                    {'backup': (io.BytesIO(payload), 'invalid.json')}, page='/backups')
    assert 'This backup is invalid' in response.text
    assert total(office, 'gross') == '250.00'


def test_empty_installation_pages_and_missing_records(app, tmp_path):
    app.config['BACKUP_DIRECTORY'] = str(tmp_path / 'empty-backups')
    client = sign_in(app.test_client(), 'treasurer')
    for path in ('/', '/members', '/transactions', '/budgets', '/reports', '/reports/export',
                 '/settings', '/backups', '/search?q=missing', '/users/me'):
        assert client.get(path).status_code == 200, path
    assert 'No academic year' in client.get('/transactions/new/Payment').text
    for path in ('/members/999999', '/transactions/999999', '/receipts/999999',
                 '/budgets/999999', '/does-not-exist'):
        assert client.get(path).status_code == 404
    assert client.get('/health').get_json() == {'status': 'ok'}
