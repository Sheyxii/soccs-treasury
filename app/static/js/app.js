/* Local-only enhancements; the server remains authoritative for all validation. */
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
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => {
  if (form.checkValidity()) { form.querySelectorAll('button[type="submit"],input[type="submit"]').forEach(button => { button.classList.add('submitting'); }); }
}));

