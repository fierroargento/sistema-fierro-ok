/* Menús de tareas: cada formulario conserva su estado y su confirmación. */
(function () {
  'use strict';
  const toggles = Array.from(document.querySelectorAll('[data-productos-menu]'));
  const dialogos = Array.from(document.querySelectorAll('[data-productos-dialogo]'));
  const raiz = document.querySelector('.productos-page');
  if (!raiz) return;
  const scrollKey = 'productos-scroll-' + raiz.dataset.organizacion;
  let retorno = null;
  function cerrarMenus() {
    toggles.forEach(b => {
      b.setAttribute('aria-expanded', 'false');
      document.getElementById(b.dataset.productosMenu).hidden = true;
    });
  }
  function abrir(clave, boton) {
    const d = dialogos.find(x => x.dataset.productosDialogo === clave);
    if (!d) return;
    retorno = boton ? boton.closest('.productos-menu-contenedor').querySelector('[data-productos-menu]') :
      toggles.find(b => b.dataset.productosMenu === ('productos-menu-' + (clave.startsWith('exportar') ? 'exportar' : 'importar')));
    cerrarMenus();
    dialogos.forEach(x => { if (x.open && x !== d) x.close(); });
    if (!d.open) d.showModal();
    d.querySelector('h2').focus({preventScroll: true});
  }
  toggles.forEach(b => {
    const menu = document.getElementById(b.dataset.productosMenu);
    b.addEventListener('click', () => {
      const estabaAbierto = !menu.hidden;
      cerrarMenus();
      if (!estabaAbierto) { menu.hidden = false; b.setAttribute('aria-expanded', 'true'); }
    });
    b.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); cerrarMenus(); menu.hidden = false; b.setAttribute('aria-expanded', 'true');
        const items = menu.querySelectorAll('[role=menuitem]');
        items[e.key === 'ArrowDown' ? 0 : items.length - 1].focus();
      }
    });
    menu.addEventListener('keydown', e => {
      const items = Array.from(menu.querySelectorAll('[role=menuitem]'));
      const i = items.indexOf(document.activeElement);
      if (['ArrowDown','ArrowUp','Home','End'].includes(e.key)) {
        e.preventDefault();
        const n = e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : (i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[n].focus();
      }
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrarMenus(); b.focus(); }
      if (e.key === 'Tab') cerrarMenus();
    });
  });
  document.querySelectorAll('[data-productos-tarea]').forEach(b => b.addEventListener('click', () => abrir(b.dataset.productosTarea, b)));
  document.addEventListener('click', e => { if (!e.target.closest('.productos-menu-contenedor')) cerrarMenus(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && toggles.some(b => b.getAttribute('aria-expanded') === 'true')) {
      const b = toggles.find(x => x.getAttribute('aria-expanded') === 'true'); cerrarMenus(); b.focus();
    }
  });
  dialogos.forEach(d => {
    d.querySelectorAll('[data-productos-tarea-cerrar]').forEach(b => b.addEventListener('click', () => d.close()));
    d.addEventListener('close', () => { if (retorno) retorno.focus({preventScroll: true}); });
    d.querySelectorAll('form').forEach(f => f.addEventListener('submit', e => {
      if (!e.defaultPrevented && f.checkValidity()) {
        try { sessionStorage.setItem(scrollKey, String(window.scrollY)); } catch (_) {}
      }
    }));
  });
  const activo = dialogos.find(d => d.hasAttribute('data-auto-open'));
  if (activo) abrir(activo.dataset.productosDialogo, null);
})();
