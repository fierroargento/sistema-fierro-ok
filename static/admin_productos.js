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

  const comboPanel = document.getElementById("producto-combo");
  const comboFilas = document.getElementById("producto-combo-filas");
  let recetas = [];
  let borradores = {};
  let unidadAnterior = "";
  function componentesActuales() {
    return Array.from(comboFilas.children).map(f => ({
      sku: f.querySelector("[data-componente-sku]").value,
      cantidad: f.querySelector("[data-componente-cantidad]").value
    }));
  }
  function estadoCombo() {
    const esCombo = form.elements.tipo.value === "combo";
    comboPanel.hidden = !esCombo;
    comboPanel.querySelectorAll("input,select,button").forEach(c => { c.disabled = !esCombo; });
    document.getElementById("producto-combo-vacio").hidden = comboFilas.children.length > 0;
  }
  function ajustarPasoCantidad(control) {
    // El mínimo fija la base del step nativo: conserva la parte decimal
    // escrita, mientras las flechas suman/restan una unidad completa.
    const fraccion = /^\d*\.(\d{1,6})$/.exec(control.value);
    control.min = fraccion && /[1-9]/.test(fraccion[1]) ? "0." + fraccion[1] : "1";
    control.step = "1";
  }
  function agregarComponente(dato) {
    const fila = document.getElementById("producto-componente-template").content.firstElementChild.cloneNode(true);
    const selector = fila.querySelector("[data-componente-sku]");
    const sku = dato ? dato.sku : "";
    if (sku && !Array.from(selector.options).some(o => o.value === sku)) {
      const o = new Option(sku + " · Revisar habilitación en Productos", sku);
      selector.add(o);
    }
    selector.value = sku;
    Array.from(selector.options).forEach(o => { if (o.value && o.value === form.elements.sku.value) o.disabled = true; });
    const cantidad = fila.querySelector("[data-componente-cantidad]");
    cantidad.value = dato ? String(dato.cantidad).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1") : "1";
    ajustarPasoCantidad(cantidad);
    cantidad.addEventListener("input", () => ajustarPasoCantidad(cantidad));
    fila.querySelector("[data-componente-quitar]").addEventListener("click", () => { fila.remove(); estadoCombo(); });
    comboFilas.appendChild(fila);
    estadoCombo();
    return selector;
  }
  function cargarComposicion(filas) {
    comboFilas.replaceChildren();
    (filas || []).forEach(agregarComponente);
    estadoCombo();
  }
  form.elements.tipo.addEventListener("change", estadoCombo);
  document.getElementById("producto-combo-agregar").addEventListener("click", () => {
    if (comboFilas.children.length < 100) agregarComponente(null).focus();
  });
  form.elements.unidad_combo_id.addEventListener("change", () => {
    borradores[unidadAnterior] = componentesActuales();
    unidadAnterior = form.elements.unidad_combo_id.value;
    const receta = recetas.find(r => String(r.unidad_combo_id || "") === unidadAnterior);
    cargarComposicion(borradores[unidadAnterior] || (receta && receta.componentes_combo) || []);
  });
  function validarCombo() {
    const aviso = document.getElementById("producto-combo-error");
    aviso.hidden = true;
    if (form.elements.tipo.value !== "combo") return true;
    const filas = componentesActuales();
    const skus = filas.map(f => f.sku);
    let error = filas.length ? "" : "Agregá al menos un producto y su cantidad para guardar el combo.";
    if (new Set(skus).size !== skus.length) error = "Hay componentes repetidos. Dejá una sola fila por producto.";
    if (skus.includes(form.elements.sku.value.trim().toUpperCase())) error = "El combo no puede contener su propio SKU.";
    if (error) {
      aviso.textContent = error; aviso.hidden = false;
      aviso.scrollIntoView({block:"nearest"});
      document.getElementById("producto-combo-agregar").focus();
      return false;
    }
    form.elements.componentes_combo_json.value = JSON.stringify(filas);
    return true;
  }

  function ajustarNoStockeable() {
    const noStockeable = form.elements.no_stockeable.checked;
    if (noStockeable) form.elements.permitir_stock_negativo.checked = false;
    form.elements.permitir_stock_negativo.disabled = noStockeable;
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
    recetas = filaGuardada ? (filaGuardada.composiciones || []) : [];
    borradores = {};
    unidadAnterior = String(valores.unidad_combo_id || "");
    form.elements.unidad_combo_id.value = unidadAnterior;
    let componentes = valores.componentes_combo || [];
    if (fallido) {
      try { componentes = JSON.parse(fallido.componentes_combo_json || "[]"); } catch (_) { componentes = []; }
    }
    document.getElementById("producto-combo-error").hidden = true;
    cargarComposicion(Array.isArray(componentes) ? componentes : []);
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
    if (enviando || (f === form && !validarCombo()) || !f.reportValidity()) return;
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
