"use strict";
document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-accounting-cancel]");
  if (!button) return;
  const editor = button.closest(".accounting-editor");
  if (!editor) return;
  editor.querySelectorAll("form").forEach(function (form) { form.reset(); });
  editor.open = false;
  editor.querySelector("summary").focus({ preventScroll: true });
});


// Restringir el calendario y bloquear rangos invertidos escritos manualmente.
document.querySelectorAll("[data-accounting-period]").forEach(function (form) {
  const desde = form.querySelector('[name="desde"]');
  const hasta = form.querySelector('[name="hasta"]');
  function validarPeriodo() {
    desde.max = hasta.value || "";
    hasta.min = desde.value || "";
    hasta.setCustomValidity(desde.value && hasta.value && desde.value > hasta.value
      ? "La fecha Hasta debe ser igual o posterior a Desde." : "");
  }
  [desde, hasta].forEach(function (input) {
    input.addEventListener("input", validarPeriodo);
    input.addEventListener("change", validarPeriodo);
  });
  form.addEventListener("submit", function (event) {
    validarPeriodo();
    if (!form.reportValidity()) event.preventDefault();
  });
  validarPeriodo();
});
