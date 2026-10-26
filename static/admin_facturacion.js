"use strict";
document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-fiscal-cancel]");
  if (!button) return;
  const editor = button.closest(".fiscal-editor");
  if (!editor) return;
  editor.querySelectorAll("form").forEach(function (form) { form.reset(); });
  editor.open = false;
  editor.querySelector("summary").focus({ preventScroll: true });
});

// La selección prepara borradores: no consulta servicios externos.
document.addEventListener("DOMContentLoaded", function () {
  const data = document.getElementById("asignaciones-fiscales");
  if (!data) return;
  const filas = JSON.parse(data.textContent);
  const form = data.closest("form");
  const sucursal = form.elements.sucursal_id;
  const entidad = form.elements.entidad_fiscal_id;
  const punto = form.elements.punto_venta_fiscal_id;
  const tipo = form.elements.tipo_comprobante_fiscal_id;
  function filtrar(select, acepta) {
    for (const option of select.options) {
      option.hidden = !!option.value && !acepta(option);
      option.disabled = option.hidden;
    }
    if (select.selectedOptions[0]?.disabled) select.value = "";
  }
  function actualizarPunto() {
    const asignados = filas.filter(a => String(a.sucursal) === sucursal.value && String(a.entidad) === entidad.value);
    filtrar(punto, o => asignados.some(a => String(a.punto) === o.value));
    if (asignados.length === 1) punto.value = String(asignados[0].punto);
    filtrar(tipo, o => o.dataset.punto === punto.value);
  }
  function actualizarSucursal() {
    const asignados = filas.filter(a => String(a.sucursal) === sucursal.value);
    filtrar(entidad, o => asignados.some(a => String(a.entidad) === o.value));
    const inicial = asignados.find(a => a.predeterminado);
    entidad.value = inicial ? String(inicial.entidad) : "";
    punto.value = ""; tipo.value = "";
    actualizarPunto();
  }
  sucursal.addEventListener("change", actualizarSucursal);
  entidad.addEventListener("change", actualizarPunto);
  punto.addEventListener("change", () => filtrar(tipo, o => o.dataset.punto === punto.value));
  form.addEventListener("reset", () => setTimeout(actualizarSucursal, 0));
  actualizarSucursal();
});
