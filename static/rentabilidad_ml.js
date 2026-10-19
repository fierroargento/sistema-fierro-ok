/* Lectura transitoria y exportación local; sin guardar archivos ni conexiones ML/MP. */
document.addEventListener('DOMContentLoaded', () => {
  const page = document.querySelector('.profitability-page');
  if (!page) return;
  let active = null;
  page.addEventListener('click', event => {
    if (event.target.closest('[data-lot-create-cancel]')) {
      if (active) active.abort();
      active = null;
      const status = page.querySelector('[data-profitability-status]');
      if (status) status.textContent = '';
    }
    if (event.target.closest('[data-profitability-download]')) {
      const source = page.querySelector('#evidencia-archivo');
      if (!source) return;
      const blob = new Blob([JSON.stringify(JSON.parse(source.textContent), null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'rentabilidad_ml_archivo_recalculado.json';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  });
  page.addEventListener('submit', async event => {
    const form = event.target.closest('[data-profitability-upload]');
    if (!form) return;
    event.preventDefault();
    if (active) return;
    const file = form.querySelector('[name="archivo"]').files[0];
    const status = form.querySelector('[data-profitability-status]');
    if (!file || !/\.json$/i.test(file.name) || file.size > 2000000 || !file.size) {
      status.textContent = 'Seleccioná un archivo .json de hasta 2 MB.';
      return;
    }
    const controller = new AbortController();
    active = controller;
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Analizando archivo…';
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': form.querySelector('[name="_csrf_token"]').value},
        body: file, signal: controller.signal
      });
      if (active !== controller) return;
      if (response.redirected) { window.location.assign(response.url); return; }
      const html = await response.text();
      if (active !== controller) return;
      const documentResult = new DOMParser().parseFromString(html, 'text/html');
      const content = documentResult.querySelector('.profitability-page');
      if (!content) throw new Error('No se pudo analizar. Recargá la pantalla para renovar la sesión y reintentá.');
      // Conserva el elemento y los listeners delegados de los diálogos compartidos.
      page.innerHTML = content.innerHTML;
      const destination = page.querySelector(response.ok ? '#resultado' : '[role="alert"]');
      if (destination) {
        if (!destination.hasAttribute('tabindex')) destination.tabIndex = -1;
        destination.focus({preventScroll: true});
        destination.scrollIntoView({block: 'start'});
      }
    } catch (error) {
      if (active === controller) status.textContent = error.name === 'AbortError'
        ? 'El análisis se interrumpió. Podés volver a intentarlo.' : error.message;
    } finally {
      clearTimeout(timer);
      if (active === controller) active = null;
      submit.disabled = false;
      form.removeAttribute('aria-busy');
    }
  });
});
