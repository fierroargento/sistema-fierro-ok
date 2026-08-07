(function () {
  "use strict";
  function iniciar() {
    const maestro = document.getElementById("seleccionar-columnas");
    const checks = Array.from(document.querySelectorAll("[data-map-check]"));
    function sincronizar(check) {
      const fila = check.closest(".mapping-row");
      const selector = fila && fila.querySelector("[data-map-select]");
      if (!selector) return;
      selector.disabled = !check.checked;
    }
    checks.forEach(function (check) {
      check.addEventListener("change", function () {
        sincronizar(check);
        if (maestro) maestro.checked = checks.every(function (item) { return item.checked; });
      });
      sincronizar(check);
    });
    if (maestro) {
      maestro.checked = checks.length > 0 && checks.every(function (item) { return item.checked; });
      maestro.addEventListener("change", function () {
        checks.forEach(function (check) { check.checked = maestro.checked; sincronizar(check); });
      });
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
