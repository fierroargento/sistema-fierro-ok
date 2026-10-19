(function () {
  "use strict";
  const contenido = document.getElementById("productos-datos");
  if (!contenido) return;
  const datos = JSON.parse(contenido.textContent);
  const dialogo = document.getElementById("producto-dialog");
  const form = document.getElementById("producto-form");
  const confirmar = document.getElementById("producto-confirm");
  const raiz = document.querySelector(".productos-page");
  const scrollKey = "productos-scroll-" + raiz.dataset.organizacion;
  let pendiente = null;
  let enviando = false;

  function ajustarNoStockeable() {
    const noStockeable = form.elements.no_stockeable.checked;
    [form.elements.permite_correo, form.elements.permite_via_cargo].forEach(c => {
      if (noStockeable) c.checked = false;
      c.disabled = noStockeable;
    });
  }
  form.elements.no_stockeable.addEventListener("change", ajustarNoStockeable);

  function abrir(fila, fallido) {
    form.reset();
    form.querySelectorAll("details").forEach(d => { d.open = false; });
    const edicion = fallido ? fallido.accion === "editar_producto" : !!fila;
    const valores = fallido || (fila && fila.datos) || {};
    for (const control of form.elements) {
      if (!control.name || !(control.name in valores)) continue;
      if (control.type === "checkbox") control.checked = valores[control.name] === true || valores[control.name] === "1";
      else control.value = valores[control.name] === null ? "" : valores[control.name];
    }
    if (fallido) {
      form.querySelectorAll('input[type="checkbox"]').forEach(c => { c.checked = fallido[c.name] === "1"; });
    }
    form.elements.accion.value = edicion ? "editar_producto" : "crear_producto";
    form.elements.producto_id.value = fallido ? (fallido.producto_id || "") : (fila ? fila.id : "");
    form.elements.huella.value = fallido ? fallido.huella : (fila ? fila.huella : "nuevo");
    form.elements.sku.readOnly = edicion;
    const filaGuardada = fila || datos.filas.find(f => String(f.id) === String(form.elements.producto_id.value));
    const tipoGuardado = filaGuardada && filaGuardada.configurado ? filaGuardada.datos.tipo : "";
    Array.from(form.elements.tipo.options).forEach(o => {
      o.disabled = edicion && !!tipoGuardado && o.value !== tipoGuardado && (tipoGuardado === "combo" || o.value === "combo");
    });
    const referencia = String(form.elements.insumo_id.value || "");
    Array.from(form.elements.insumo_id.options).forEach(o => { o.disabled = edicion && !!referencia && o.value !== referencia; });
    document.getElementById("producto-dialog-title").textContent = edicion ? "Gestionar · " + valores.sku : "Nuevo producto";
    const aviso = document.getElementById("producto-form-error");
    aviso.hidden = !fallido;
    aviso.textContent = fallido ? datos.error : "";
    ajustarNoStockeable();
    dialogo.showModal();
    (edicion ? form.elements.nombre : form.elements.sku).focus();
  }
  document.querySelectorAll("[data-new-product]").forEach(b => b.addEventListener("click", () => abrir(null, null)));
  document.querySelectorAll("[data-edit-product]").forEach(b => b.addEventListener("click", () => {
    abrir(datos.filas.find(f => String(f.id) === b.dataset.editProduct), null);
  }));
  document.querySelectorAll("[data-close-product]").forEach(b => b.addEventListener("click", () => dialogo.close()));
  form.addEventListener("keydown", e => {
    if (e.key === "Enter" && e.target.tagName !== "TEXTAREA" && e.target.tagName !== "BUTTON") e.preventDefault();
  });
  confirmar.addEventListener("keydown", e => { if (e.key === "Enter") e.preventDefault(); });
  confirmar.addEventListener("cancel", () => { pendiente = null; });
  document.getElementById("producto-confirm-cancel").addEventListener("click", () => { confirmar.close(); pendiente = null; });
  document.getElementById("producto-confirm-ok").addEventListener("click", () => {
    if (!pendiente || enviando) return;
    const destino = pendiente;
    pendiente = null;
    confirmar.close();
    enviando = true;
    try { sessionStorage.setItem(scrollKey, String(window.scrollY)); } catch (_) {}
    destino.querySelectorAll('button[type="submit"]').forEach(b => { b.disabled = true; b.textContent = "Guardando…"; });
    HTMLFormElement.prototype.submit.call(destino);
  });
  document.querySelectorAll("[data-confirm-save]").forEach(f => f.addEventListener("submit", e => {
    e.preventDefault();
    if (enviando || !f.reportValidity()) return;
    pendiente = f;
    document.getElementById("producto-confirm-text").textContent = f.dataset.confirmSave;
    confirmar.showModal();
    document.getElementById("producto-confirm-cancel").focus();
  }));
  document.querySelectorAll("[data-import-open]").forEach(b => b.addEventListener("click", () => {
    const panel = document.getElementById("productos-importacion");
    panel.open = true;
    panel.scrollIntoView({behavior:"smooth", block:"start"});
  }));
  try {
    const scroll = sessionStorage.getItem(scrollKey);
    if (scroll !== null) { sessionStorage.removeItem(scrollKey); requestAnimationFrame(() => window.scrollTo(0, Number(scroll))); }
  } catch (_) {}
  if (datos.formulario_error) abrir(null, datos.formulario_error);
})();
