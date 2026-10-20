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

  const pasos = Array.from(form.querySelectorAll("[data-paso]")).filter(p =>
    form.elements.datos_generales_presentados || !["comercial", "imagenes"].includes(p.dataset.paso));
  const anterior = document.getElementById("producto-anterior");
  const siguiente = document.getElementById("producto-siguiente");
  const guardar = document.getElementById("producto-guardar");
  let pasoActual = 0;
  let maxVisitado = 0;
  const indicador = document.getElementById("producto-pasos-indicador");
  pasos.forEach((p, i) => {
    const li = document.createElement("li"), boton = document.createElement("button");
    boton.type = "button"; boton.textContent = String(i + 1);
    boton.setAttribute("aria-label", "Paso " + (i + 1) + ": " + p.dataset.titulo);
    boton.title = p.dataset.titulo;
    boton.addEventListener("click", () => { if (i <= maxVisitado) mostrarPaso(i); });
    li.appendChild(boton); indicador.appendChild(li);
  });
  function mostrarPaso(indice, enfocar = true) {
    pasoActual = indice;
    maxVisitado = Math.max(maxVisitado, indice);
    pasos.forEach((p, i) => { p.hidden = i !== indice; });
    Array.from(indicador.querySelectorAll("button")).forEach((b, i) => {
      b.disabled = i > maxVisitado;
      if (i === indice) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      b.dataset.completado = String(i < indice);
    });
    document.getElementById("producto-paso-progreso").textContent =
      "Paso " + (indice + 1) + " de " + pasos.length + " · " + pasos[indice].dataset.titulo;
    anterior.hidden = indice === 0;
    const ultimo = indice === pasos.length - 1;
    siguiente.hidden = ultimo; guardar.hidden = !ultimo;
    siguiente.textContent = indice === pasos.length - 2 ? "Revisar ficha" : "Siguiente";
    if (ultimo) armarResumen();
    dialogo.querySelector(".producto-dialog-body").scrollTop = 0;
    if (enfocar) pasos[indice].querySelector(".producto-paso-titulo").focus();
  }
  function irAPaso(nombre) {
    const i = pasos.findIndex(p => p.dataset.paso === nombre);
    if (i >= 0) mostrarPaso(i);
  }
  function armarResumen() {
    const destino = document.getElementById("producto-resumen");
    destino.replaceChildren();
    pasos.slice(0, -1).forEach((p, i) => {
      const tarjeta = document.createElement("section"), cabecera = document.createElement("div");
      tarjeta.className = "producto-resumen-card";
      const titulo = document.createElement("h4"); titulo.textContent = p.dataset.titulo;
      const editar = document.createElement("button"); editar.type = "button";
      editar.className = "secondary-link"; editar.textContent = "Editar";
      editar.setAttribute("aria-label", "Editar " + p.dataset.titulo);
      editar.addEventListener("click", () => mostrarPaso(i));
      cabecera.append(titulo, editar); tarjeta.appendChild(cabecera);
      const lista = document.createElement("dl");
      p.querySelectorAll("label").forEach(label => {
        const c = label.querySelector("input,select,textarea");
        if (!c || c.disabled || ["hidden", "file", "radio"].includes(c.type)) return;
        const copia = label.cloneNode(true);
        copia.querySelectorAll("input,select,textarea,datalist").forEach(n => n.remove());
        const nombre = copia.textContent.trim();
        if (!nombre) return;
        const dt = document.createElement("dt"), dd = document.createElement("dd");
        dt.textContent = nombre;
        dd.textContent = c.type === "checkbox" ? (c.checked ? "Sí" : "No") :
          c.tagName === "SELECT" ? (c.value ? c.selectedOptions[0].textContent : "Sin definir") :
          (c.value.trim() || "Sin completar");
        lista.append(dt, dd);
      });
      if (p.dataset.paso === "imagenes") {
        const dt = document.createElement("dt"), dd = document.createElement("dd");
        dt.textContent = "Fotos";
        const fotos = Array.from(p.querySelectorAll(".producto-imagen"));
        dd.textContent = fotos.length ? fotos.map(f => f.querySelector("span").textContent +
          (f.querySelector("input[type=radio]").checked ? " (principal)" : "")).join(" · ") : "Sin fotos";
        lista.append(dt, dd);
      }
      if (p.dataset.paso === "costos" && form.elements.tipo.value === "produccion" && window.productosProduccion) {
        const dt=document.createElement("dt"), dd=document.createElement("dd");
        dt.textContent="Costo de fabricación"; dd.textContent=window.productosProduccion.resumen(); lista.append(dt,dd);
      }
      tarjeta.appendChild(lista); destino.appendChild(tarjeta);
    });
  }
  function validarPaso(indice) {
    const panel = pasos[indice];
    const invalido = Array.from(panel.querySelectorAll("input,select,textarea")).find(c => c.willValidate && !c.validity.valid);
    if (invalido) { mostrarPaso(indice); if (window.productosProduccion) window.productosProduccion.mostrarError(invalido); invalido.reportValidity(); return false; }
    if (panel.dataset.paso === "costos" && !validarCombo()) { mostrarPaso(indice); return false; }
    if (panel.dataset.paso === "costos" && window.productosProduccion && !window.productosProduccion.validar()) { mostrarPaso(indice); return false; }
    if (window.productosDatos && !window.productosDatos.validar(panel.dataset.paso)) return false;
    return true;
  }
  function validarFicha() {
    for (let i = 0; i < pasos.length - 1; i++) if (!validarPaso(i)) return false;
    return true;
  }
  anterior.addEventListener("click", () => mostrarPaso(pasoActual - 1));
  siguiente.addEventListener("click", () => {
    if (!validarPaso(pasoActual)) return;
    if (pasoActual === pasos.length - 2 && !validarFicha()) return;
    mostrarPaso(pasoActual + 1);
  });
  form.addEventListener("producto-error-paso", e => irAPaso(e.detail));

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
    pasoActual = 0; maxVisitado = 0;
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
    if (window.productosDatos) window.productosDatos.abrir(filaGuardada, fallido);
    if (window.productosProduccion) window.productosProduccion.abrir(filaGuardada, fallido);
    mostrarPaso(0, false);
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
  function validarCampos(f) {
    const invalido = Array.from(f.elements).find(c => c.willValidate && !c.validity.valid);
    if (invalido) {
      let padre = invalido.parentElement;
      while (padre && padre !== f) { if (padre.tagName === "DETAILS") padre.open = true; padre = padre.parentElement; }
    }
    return f.reportValidity();
  }
  document.querySelectorAll("[data-confirm-save]").forEach(f => f.addEventListener("submit", e => {
    e.preventDefault();
    if (enviando) return;
    if (f === form) {
      // Un submit anticipado tampoco guarda: lleva a la revisión explícita.
      if (!validarFicha()) return;
      if (pasoActual !== pasos.length - 1) { mostrarPaso(pasos.length - 1); return; }
    } else if (!validarCampos(f)) return;
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
