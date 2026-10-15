/* Cancelar nunca envía el formulario. La navegación conserva la posición. */
(() => {
  const page = document.querySelector('.crm-page');
  if (!page) return;
  const scrollKey = 'fierro:crm:scroll:' + location.pathname;
  page.querySelectorAll('[data-crm-cancel]').forEach(button => {
    button.addEventListener('click', () => {
      const form = button.closest('form');
      const editor = button.closest('details');
      form.reset();
      editor.open = false;
      editor.querySelector('summary').focus({preventScroll: true});
    });
  });
  page.querySelectorAll('.crm-create-form').forEach(form => {
    form.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.isComposing &&
          event.target.matches('input:not([type=submit]):not([type=button])')) {
        event.preventDefault();
      }
    });
  });
  page.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      try { sessionStorage.setItem(scrollKey, String(window.scrollY)); } catch (_) {}
    });
  });
  try {
    const stored = sessionStorage.getItem(scrollKey);
    sessionStorage.removeItem(scrollKey);
    const y = Number(stored);
    if (stored !== null && Number.isFinite(y) && y >= 0) {
      requestAnimationFrame(() => window.scrollTo({top: y, behavior: 'instant'}));
    }
  } catch (_) {}
})();
