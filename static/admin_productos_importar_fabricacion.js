/* Estado visible al analizar archivos; no envía ni guarda por su cuenta. */
(function () {
  'use strict';
  document.querySelectorAll('.fabricacion-import-form, .productos-planilla-form').forEach(function (form) {
    let analizando = false;
    const boton = form.querySelector('button[type="submit"]');
    const estado = form.querySelector('[data-fabricacion-progreso]');
    const texto = boton.textContent;
    form.addEventListener('submit', function (event) {
      if (analizando) { event.preventDefault(); return; }
      if (!form.checkValidity()) { event.preventDefault(); form.reportValidity(); return; }
      analizando = true;
      boton.disabled = true;
      boton.textContent = 'Revisando…';
      form.setAttribute('aria-busy', 'true');
      estado.hidden = false;
      estado.textContent = 'Estamos revisando los datos de la planilla. Todavía no se guarda ningún producto.';
    });
    window.addEventListener('pageshow', function () {
      if (!analizando) return;
      analizando = false;
      boton.disabled = false;
      boton.textContent = texto;
      form.removeAttribute('aria-busy');
      estado.hidden = true;
    });
  });
})();
