"use strict";
document.addEventListener("DOMContentLoaded", function () {
  const destinos = {crear_proveedor:"proveedores", crear_orden:"ordenes", agregar_item:"ordenes", quitar_item:"ordenes", cambiar_estado:"ordenes", preparar_recepcion:"recepciones", registrar_factura:"facturas", preparar_impactos:"propuestas", crear_mapeo_inventario:"mapeos", decidir_impacto:"propuestas"};
  document.querySelectorAll('.compras-page a[href^="#orden-editor-"], .compras-page a[href^="#recepcion-editor-"]').forEach(function (enlace) {
    enlace.addEventListener("click", function () {
      const fila = document.getElementById(enlace.hash.slice(1));
      const editor = fila && fila.querySelector("details");
      if (editor) editor.open = true;
    });
  });
  const clave = "compras-continuar:" + location.pathname;
  document.querySelectorAll(".compras-page form").forEach(function (formulario) {
    formulario.addEventListener("submit", function () {
      const accion = formulario.querySelector('[name="accion"]');
      if (accion && destinos[accion.value]) {
        try { sessionStorage.setItem(clave, "compras-" + destinos[accion.value]); } catch (_) {}
      }
    });
  });
  let destino;
  try { destino = sessionStorage.getItem(clave); sessionStorage.removeItem(clave); } catch (_) {}
  const bloque = destino && document.getElementById(destino);
  if (bloque && (new URLSearchParams(location.search).has("ok") || new URLSearchParams(location.search).has("error"))) {
    const aviso = document.querySelector(".compras-page .feedback");
    if (aviso) bloque.prepend(aviso);
    requestAnimationFrame(function () { bloque.scrollIntoView({block:"start"}); });
  }
});
