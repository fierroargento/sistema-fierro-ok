"use strict";
(() => {
  const confirmar = document.getElementById("modulo-confirmacion");
  if (!confirmar) return;
  let pendiente = null;
  let enviando = false;
  const origenes = new WeakMap();
  document.querySelectorAll("[data-modulo-abrir]").forEach(boton => {
    boton.addEventListener("click", () => {
      const dialogo = document.getElementById(boton.dataset.moduloAbrir);
      origenes.set(dialogo, boton);
      dialogo.showModal();
    });
  });
  document.querySelectorAll(".configuracion-dialogo form").forEach(form => {
    const dialogo = form.closest("dialog");
    form.querySelector("[data-modulo-cerrar]").addEventListener("click", () => dialogo.close());
    dialogo.addEventListener("close", () => {
      form.reset();
      origenes.get(dialogo)?.focus({preventScroll: true});
    });
    form.addEventListener("submit", event => {
      if (enviando) return;
      event.preventDefault();
      if (!form.reportValidity()) return;
      pendiente = form;
      confirmar.showModal();
      document.getElementById("modulo-no").focus();
    });
  });
  document.getElementById("modulo-no").addEventListener("click", () => confirmar.close());
  confirmar.addEventListener("close", () => { pendiente = null; });
  document.getElementById("modulo-si").addEventListener("click", () => {
    if (!pendiente || enviando) return;
    const form = pendiente;
    if (!form.reportValidity()) return;
    enviando = true;
    document.getElementById("modulo-si").disabled = true;
    form.requestSubmit();
  });
})();
