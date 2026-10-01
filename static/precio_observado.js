(function () {
  "use strict";
  const dialog = document.getElementById("observed-price-dialog");
  const form = document.getElementById("observed-price-form");
  let trigger;
  if (dialog && form) {
    document.querySelectorAll("[data-observed-price]").forEach(function (button) {
      button.addEventListener("click", function () {
        trigger = button;
        form.reset();
        ["lista_precio_id", "catalogo_producto_id", "observacion_id", "cuenta_codigo", "referencia_publicacion", "precio_publicado"].forEach(function (name) {
          form.elements.namedItem(name).value = button.getAttribute("data-" + name) || "";
        });
        dialog.querySelector("[data-price-context]").textContent = button.getAttribute("data-context") || "";
        dialog.showModal();
        form.elements.namedItem("precio_publicado").focus();
      });
    });
    dialog.querySelectorAll("[data-price-close]").forEach(function (button) { button.addEventListener("click", function () { dialog.close(); }); });
    dialog.addEventListener("click", function (event) {
      if (event.target !== dialog) return;
      const box = dialog.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
    });
    dialog.addEventListener("close", function () { form.reset(); if (trigger) trigger.focus({ preventScroll: true }); });
    form.addEventListener("submit", function (event) {
      if (!window.confirm("¿Confirmás el nuevo precio observado? Se guardará en el historial interno.")) event.preventDefault();
    });
  }
  const section = new URLSearchParams(location.search).get("seccion");
  if (section === "control-comercial" || location.hash === "#control-comercial") {
    requestAnimationFrame(function () { const target = document.getElementById("control-comercial"); if (target) target.scrollIntoView({ block: "start" }); });
  }
})();
