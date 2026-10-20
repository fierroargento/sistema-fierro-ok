/* Presentación compartida de acciones explícitas. No cambia enlaces, eventos ni formularios. */
(() => {
  'use strict';
  const selector = 'button[data-fierro-icon], a[data-fierro-icon], summary[data-fierro-icon]';
  const ns = 'http://www.w3.org/2000/svg';
  const figuras = {
    ver: [['path', {d: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z'}], ['circle', {cx: 12, cy: 12, r: 3}]],
    gestionar: [['path', {d: 'm9.2 3-.5 2.2-1.6.9-2.2-.7-2.8 4.8 1.7 1.5v1.8l-1.7 1.5 2.8 4.8 2.2-.7 1.6.9.5 2.2h5.6l.5-2.2 1.6-.9 2.2.7 2.8-4.8-1.7-1.5v-1.8l1.7-1.5-2.8-4.8-2.2.7-1.6-.9L14.8 3Z'}], ['circle', {cx: 12, cy: 12, r: 3}]]
  };
  function decorar(control) {
    if (!control.isConnected || control.dataset.fierroIconReady || !figuras[control.dataset.fierroIcon]) return;
    const texto = control.textContent.replace(/\s+/g, ' ').trim();
    const nombre = control.getAttribute('aria-label') || texto;
    if (!nombre) return;
    // Los nombres y textos se conservan, también para lectores de pantalla y scripts existentes.
    if (!control.hasAttribute('title')) control.title = nombre;
    if (!control.hasAttribute('aria-label')) control.setAttribute('aria-label', nombre);
    const etiqueta = document.createElement('span');
    etiqueta.className = 'fierro-action-label';
    while (control.firstChild) etiqueta.append(control.firstChild);
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    for (const [tipo, atributos] of figuras[control.dataset.fierroIcon]) {
      const figura = document.createElementNS(ns, tipo);
      for (const [clave, valor] of Object.entries(atributos)) figura.setAttribute(clave, valor);
      svg.append(figura);
    }
    control.append(svg, etiqueta);
    control.classList.add('fierro-icon-action');
    control.dataset.fierroIconReady = '1';
  }
  function preparar(raiz) {
    if (raiz.nodeType !== 1 && raiz.nodeType !== 9) return;
    if (raiz.matches?.(selector)) decorar(raiz);
    raiz.querySelectorAll(selector).forEach(decorar);
  }
  preparar(document);
  // Incluye filas y emergentes incorporados después de la carga inicial.
  new MutationObserver(cambios => {
    for (const cambio of cambios) for (const nodo of cambio.addedNodes) if (nodo.isConnected) preparar(nodo);
  }).observe(document.body, {childList: true, subtree: true});
})();
