(() => {
  'use strict';
  document.querySelectorAll('[data-consulta-ver]').forEach(boton => {
    const dialogo = document.getElementById(boton.dataset.consultaVer);
    if (!dialogo) return;
    boton.addEventListener('click', () => {
      dialogo.querySelectorAll('[data-consulta-src]').forEach(img => {
        if (!img.hasAttribute('src')) img.src = img.dataset.consultaSrc;
      });
      if (!dialogo.open) dialogo.showModal();
    });
    dialogo.querySelectorAll('[data-consulta-cerrar]').forEach(cerrar => {
      cerrar.addEventListener('click', () => dialogo.close());
    });
    dialogo.addEventListener('close', () => boton.focus({preventScroll:true}));
  });
})();
