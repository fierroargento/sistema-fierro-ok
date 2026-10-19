(function () {
  "use strict";
  document.querySelectorAll("[data-economic-evidence]").forEach(function (form) {
    const modo = form.querySelector('[name="modo_embalaje"]');
    const adicional = form.querySelector('[name="embalaje_adicional"]');
    const lineas = form.querySelectorAll('[name="detalle_embalaje_id"]');
    function actualizar() {
      adicional.disabled = modo.value !== "adicional";
      lineas.forEach(function (linea) { linea.disabled = modo.value !== "incluido"; });
    }
    modo.addEventListener("change", actualizar);
    actualizar();
    const dialogo = form.closest("dialog");
    if (dialogo) dialogo.addEventListener("close", function () {
      queueMicrotask(function () { form.reset(); actualizar(); });
    });
    form.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && event.target.tagName !== "TEXTAREA" && event.target.tagName !== "BUTTON") event.preventDefault();
    });
    form.addEventListener("submit", function (event) {
      if (!window.confirm("¿Guardar esta evidencia interna y recalcular el precio? No se publicará ni se modificará stock.")) event.preventDefault();
    });
  });
}());
