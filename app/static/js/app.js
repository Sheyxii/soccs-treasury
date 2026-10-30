/* Local-only enhancements; the server remains authoritative for all validation. */

/* Sign-in page: password recovery dialog and show/hide password. */
const recoveryDialog = document.getElementById('password-recovery');
document.querySelector('.login-forgot')?.addEventListener('click', () => recoveryDialog?.showModal());
document.querySelector('.password-toggle')?.addEventListener('click', function () {
  const input = document.getElementById('password');
  const visible = input.type === 'text';
  input.type = visible ? 'password' : 'text';
  this.querySelector('img').src = visible ? this.dataset.showIcon : this.dataset.hideIcon;
  this.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
  this.setAttribute('aria-pressed', String(!visible));
});
document.querySelector('.mobile-toggle')?.addEventListener('click', function () {
  const open = document.body.classList.toggle('menu-open');
  this.setAttribute('aria-expanded', String(open));
});

const menuToggle = document.querySelector('.mobile-toggle');
const navigation = document.getElementById('officer-nav');
const closeMenu = () => {
  document.body.classList.remove('menu-open');
  menuToggle?.setAttribute('aria-expanded', 'false');
};
document.addEventListener('click', event => {
  if (document.body.classList.contains('menu-open') && !navigation?.contains(event.target) && !menuToggle?.contains(event.target)) closeMenu();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.body.classList.contains('menu-open')) {
    closeMenu();
    menuToggle?.focus();
  }
});
document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
const options = document.getElementById('transaction-options');
if (options) {
  const data = JSON.parse(options.textContent);
  const year = document.getElementById('academic_year_id');
  const amount = document.getElementById('amount');
  year?.addEventListener('change', () => { if (data.fees[year.value]) amount.value = data.fees[year.value]; });
  const category = document.getElementById('category_id');
  const update = () => {
    const box = document.getElementById('budget-feedback');
    if (!box || !category?.value || data.categories[category.value] === undefined) return;
    const remaining = Number(data.categories[category.value]);
    box.textContent = Number(amount.value) > remaining ? 'This expense exceeds the category balance and will be held for approval.' : 'Remaining after this expense: ₱' + (remaining - Number(amount.value || 0)).toLocaleString('en-PH', {minimumFractionDigits:2, maximumFractionDigits:2});
  };
  category?.addEventListener('change', update); amount?.addEventListener('input', update); update();
}
/* Press "/" anywhere (outside a text field) to jump to the top search bar. */
const topSearch = document.querySelector('.topbar-search input');
document.addEventListener('keydown', event => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
  if (event.key === '/' && topSearch && !typing) { event.preventDefault(); topSearch.focus(); topSearch.select(); }
});

/* Live search suggestions under the top search bar. */
const searchForm = document.querySelector('.topbar-search[data-suggest-url]');
if (searchForm && topSearch) {
  const list = searchForm.querySelector('.search-suggestions');
  const status = searchForm.querySelector('[data-suggest-status]');
  let timer = null, controller = null, items = [], active = -1, lastQuery = '';

  // Builds text with each matched word wrapped in <mark>, using DOM nodes only (no HTML injection).
  const highlight = (text, words) => {
    const fragment = document.createDocumentFragment();
    const escaped = words.filter(Boolean).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    if (!escaped.length) { fragment.append(text); return fragment; }
    const pattern = new RegExp('(' + escaped.join('|') + ')', 'ig');
    text.split(pattern).forEach((part, i) => {
      if (!part) return;
      if (i % 2) { const mark = document.createElement('mark'); mark.textContent = part; fragment.append(mark); }
      else fragment.append(part);
    });
    return fragment;
  };
  const close = () => {
    list.hidden = true; list.replaceChildren(); items = []; active = -1;
    topSearch.setAttribute('aria-expanded', 'false'); topSearch.removeAttribute('aria-activedescendant');
  };
  const setActive = index => {
    items.forEach((el, i) => el.setAttribute('aria-selected', String(i === index)));
    active = index;
    if (index >= 0) { topSearch.setAttribute('aria-activedescendant', items[index].id); items[index].scrollIntoView({block: 'nearest'}); }
    else topSearch.removeAttribute('aria-activedescendant');
  };
  const option = (entry, words, kind) => {
    const a = document.createElement('a');
    a.href = entry.url; a.className = 'suggestion'; a.setAttribute('role', 'option'); a.id = 'suggestion-' + items.length; a.tabIndex = -1;
    const icon = document.createElement('span'); icon.className = 'suggestion-icon ' + kind; icon.textContent = kind === 'member' ? (entry.label[0] || '?').toUpperCase() : '₱';
    icon.setAttribute('aria-hidden', 'true');
    const body = document.createElement('span'); body.className = 'suggestion-body';
    const title = document.createElement('strong'); title.append(highlight(entry.label, words));
    const detail = document.createElement('small'); detail.append(highlight(entry.detail, words));
    body.append(title, detail); a.append(icon, body);
    if (entry.amount) {
      const side = document.createElement('span'); side.className = 'suggestion-side';
      const amount = document.createElement('b'); amount.textContent = entry.amount;
      const badge = document.createElement('span'); badge.className = 'status-badge status-' + entry.status.toLowerCase(); badge.textContent = entry.status;
      side.append(amount, badge); a.append(side);
    }
    a.addEventListener('mousemove', () => setActive(items.indexOf(a)));
    items.push(a);
    return a;
  };
  const group = (label, entries, words, kind) => {
    if (!entries.length) return;
    const heading = document.createElement('div'); heading.className = 'suggestion-group'; heading.textContent = label; heading.setAttribute('role', 'presentation');
    list.append(heading);
    entries.forEach(entry => list.append(option(entry, words, kind)));
  };
  const render = data => {
    list.replaceChildren(); items = []; active = -1;
    const words = data.q.split(/\s+/).filter(Boolean);
    group('Members', data.members, words, 'member');
    group('Transactions', data.transactions, words, 'transaction');
    const total = data.members.length + data.transactions.length;
    if (!total) {
      const none = document.createElement('div'); none.className = 'suggestion-empty';
      none.textContent = 'No matches for “' + data.q + '”. Try a shorter name, a student number or a TXN number.';
      list.append(none);
    }
    const all = document.createElement('a'); all.href = data.all_url; all.className = 'suggestion suggestion-all'; all.setAttribute('role', 'option'); all.id = 'suggestion-' + items.length; all.tabIndex = -1;
    all.textContent = 'See all results for “' + data.q + '”';
    all.addEventListener('mousemove', () => setActive(items.indexOf(all)));
    items.push(all); list.append(all);
    list.hidden = false; topSearch.setAttribute('aria-expanded', 'true');
    status.textContent = total ? total + ' suggestion' + (total === 1 ? '' : 's') + ' available' : 'No matches';
  };
  const fetchSuggestions = () => {
    const q = topSearch.value.trim();
    if (q.length < 2) { close(); lastQuery = ''; return; }
    if (q === lastQuery && !list.hidden) return;
    lastQuery = q;
    controller?.abort();
    controller = new AbortController();
    searchForm.classList.add('is-loading');
    fetch(searchForm.dataset.suggestUrl + '?q=' + encodeURIComponent(q), {signal: controller.signal, headers: {Accept: 'application/json'}})
      .then(r => r.ok && r.headers.get('content-type')?.includes('json') ? r.json() : Promise.reject())
      .then(data => { if (data.q === topSearch.value.trim()) render(data); })
      .catch(() => {})
      .finally(() => searchForm.classList.remove('is-loading'));
  };
  topSearch.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(fetchSuggestions, 180); });
  topSearch.addEventListener('focus', () => { if (topSearch.value.trim().length >= 2) { lastQuery = ''; fetchSuggestions(); } });
  topSearch.addEventListener('keydown', event => {
    if (list.hidden || !items.length) return;
    if (event.key === 'ArrowDown') { event.preventDefault(); setActive((active + 1) % items.length); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); setActive(active <= 0 ? items.length - 1 : active - 1); }
    else if (event.key === 'Enter' && active >= 0) { event.preventDefault(); window.location.href = items[active].href; }
    else if (event.key === 'Escape') { event.preventDefault(); close(); }
  });
  document.addEventListener('click', event => { if (!searchForm.contains(event.target)) close(); });
  searchForm.addEventListener('focusout', event => { if (!searchForm.contains(event.relatedTarget)) setTimeout(() => { if (!searchForm.contains(document.activeElement)) close(); }, 120); });
}

/* Interactive dashboard: range, series toggles, tooltips, allocation highlight, activity filter. */
const peso = value => '₱' + Number(value).toLocaleString('en-PH', {minimumFractionDigits: 2, maximumFractionDigits: 2});
const chartPanel = document.querySelector('[data-chart]');
if (chartPanel) {
  const months = [...chartPanel.querySelectorAll('.chart-month')];
  const tooltip = chartPanel.querySelector('[data-tooltip]');
  const shown = {income: true, expense: true};
  let range = 6;
  const render = () => {
    const visible = months.slice(-range);
    months.forEach(m => { m.hidden = !visible.includes(m); });
    const max = Math.max(1, ...visible.flatMap(m => [shown.income ? +m.dataset.income : 0, shown.expense ? +m.dataset.expense : 0]));
    let income = 0, expense = 0;
    visible.forEach(m => {
      income += +m.dataset.income; expense += +m.dataset.expense;
      m.querySelector('.income-bar').style.height = (shown.income ? +m.dataset.income / max * 100 : 0) + '%';
      m.querySelector('.expense-bar').style.height = (shown.expense ? +m.dataset.expense / max * 100 : 0) + '%';
      m.querySelector('.income-bar').hidden = !shown.income;
      m.querySelector('.expense-bar').hidden = !shown.expense;
    });
    chartPanel.querySelector('[data-sum="income"]').textContent = peso(income);
    chartPanel.querySelector('[data-sum="expense"]').textContent = peso(expense);
    const net = chartPanel.querySelector('[data-sum="net"]');
    net.textContent = peso(income - expense);
    net.classList.toggle('text-danger', income - expense < 0);
  };
  chartPanel.querySelectorAll('[data-range]').forEach(button => button.addEventListener('click', () => {
    range = +button.dataset.range;
    chartPanel.querySelectorAll('[data-range]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    render();
  }));
  chartPanel.querySelectorAll('[data-series]').forEach(button => button.addEventListener('click', () => {
    const key = button.dataset.series;
    if (shown[key] && !shown[key === 'income' ? 'expense' : 'income']) return; // keep at least one series
    shown[key] = !shown[key];
    button.setAttribute('aria-pressed', String(shown[key]));
    render();
  }));
  const show = month => {
    const net = month.dataset.income - month.dataset.expense;
    tooltip.innerHTML = '';
    const title = document.createElement('strong'); title.textContent = month.dataset.label; tooltip.append(title);
    [['Income', month.dataset.income, 'legend-income'], ['Expenses', month.dataset.expense, 'legend-expense'], ['Net', net, '']].forEach(([label, value, cls]) => {
      const row = document.createElement('div');
      row.innerHTML = `<span><i class="${cls}"></i>${label}</span>`;
      const amount = document.createElement('b'); amount.textContent = peso(value); row.append(amount);
      tooltip.append(row);
    });
    if (month.tagName === 'A') { const hint = document.createElement('small'); hint.textContent = 'Click to open this month’s report'; tooltip.append(hint); }
    tooltip.hidden = false;
    const wrap = tooltip.parentElement.getBoundingClientRect(), box = month.getBoundingClientRect();
    const left = Math.min(Math.max(box.left - wrap.left + box.width / 2 - tooltip.offsetWidth / 2, 0), wrap.width - tooltip.offsetWidth);
    tooltip.style.left = left + 'px';
    months.forEach(m => m.classList.toggle('is-active', m === month));
  };
  const hide = () => { tooltip.hidden = true; months.forEach(m => m.classList.remove('is-active')); };
  months.forEach(month => {
    month.addEventListener('mouseenter', () => show(month));
    month.addEventListener('focus', () => show(month));
    month.addEventListener('mouseleave', hide);
    month.addEventListener('blur', hide);
  });
  render();
}
document.querySelectorAll('.allocation-row[data-share]').forEach(row => {
  const panel = row.closest('.panel');
  const highlight = index => panel.querySelectorAll('[data-share]').forEach(el => el.classList.toggle('is-dim', index !== null && el.dataset.share !== index));
  ['mouseenter', 'focus'].forEach(type => row.addEventListener(type, () => highlight(row.dataset.share)));
  ['mouseleave', 'blur'].forEach(type => row.addEventListener(type, () => highlight(null)));
});
document.querySelectorAll('.donut-segment').forEach(segment => {
  const panel = segment.closest('.panel');
  segment.addEventListener('mouseenter', () => panel.querySelectorAll('[data-share]').forEach(el => el.classList.toggle('is-dim', el.dataset.share !== segment.dataset.share)));
  segment.addEventListener('mouseleave', () => panel.querySelectorAll('[data-share]').forEach(el => el.classList.remove('is-dim')));
});
document.querySelectorAll('.activity-filter').forEach(group => {
  const rows = group.parentElement.querySelectorAll('[data-activity] tbody tr[data-kind]');
  group.querySelectorAll('button').forEach(button => button.addEventListener('click', () => {
    group.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    rows.forEach(row => { row.hidden = button.dataset.kind !== 'All' && row.dataset.kind !== button.dataset.kind; });
  }));
});

/* Ask before destructive actions such as deleting a member. */
document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => {
  if (!window.confirm(form.dataset.confirm)) { event.preventDefault(); event.stopImmediatePropagation(); }
}));

/* Student number: digits only, hyphen added automatically (1234-5678). */
document.querySelectorAll('input[data-student-number]').forEach(input => {
  const format = () => {
    const digits = input.value.replace(/\D/g, '').slice(0, 8);
    input.value = digits.length > 4 ? digits.slice(0, 4) + '-' + digits.slice(4) : digits;
  };
  input.addEventListener('input', format);
  input.addEventListener('keydown', event => {
    if (event.key.length === 1 && !/[0-9-]/.test(event.key) && !event.ctrlKey && !event.metaKey) event.preventDefault();
  });
  format();
});

document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => {
  if (form.checkValidity()) { form.querySelectorAll('button[type="submit"],input[type="submit"]').forEach(button => { button.classList.add('submitting'); }); }
}));

