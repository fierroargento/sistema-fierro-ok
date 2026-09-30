(function () {
  "use strict";

  function iniciarCriteriosDistribucion() {
    document.querySelectorAll("[data-production-cost]").forEach(function (control) {
      const distribucion = control.form.querySelector("[data-distribution]");
      if (!distribucion) return;

      function sincronizar() {
        const informativo = control.value === "0";
        if (informativo) distribucion.value = "sin_distribuir";
        distribucion.setAttribute("aria-disabled", String(informativo));
      }

      control.addEventListener("change", sincronizar);
      sincronizar();
    });
  }

  function iniciarPeriodicidadCostos() {
    document.querySelectorAll("[data-cost-periodicity]").forEach(function (control) {
      const formulario = control.form;
      const contenedor = formulario && formulario.querySelector("[data-eventual-months]");
      if (!contenedor) return;
      const meses = contenedor.querySelector('[name="meses_cobertura"]');

      function sincronizar() {
        const eventual = control.value === "eventual";
        contenedor.hidden = !eventual;
        meses.disabled = !eventual;
        meses.required = eventual;
        if (!eventual) meses.value = "";
      }

      control.addEventListener("change", sincronizar);
      sincronizar();
    });
  }

  function abrirDialogosDeGestion() {
    document.querySelectorAll(".source-row-action, .compras-page td > details").forEach(function (detalle) {
      if (detalle.closest("dialog, .compras-editor-row")) return;
      const resumen = detalle.querySelector(":scope > summary");
      const panel = detalle.querySelector(":scope > .source-row-panel") || document.createElement("div");
      panel.classList.add("source-row-panel");
      if (!panel.parentElement) {
        Array.from(detalle.children).forEach(function (hijo) {
          if (hijo !== resumen) panel.append(hijo);
        });
      }
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "source-dialog-trigger";
      boton.setAttribute("data-source-dialog", "");
      boton.textContent = resumen ? resumen.textContent.trim() : "Gestionar";
      const dialogo = document.createElement("dialog");
      dialogo.className = "source-dialog";
      const cerrar = document.createElement("button");
      cerrar.type = "button";
      cerrar.className = "source-dialog-close";
      cerrar.setAttribute("aria-label", "Cerrar");
      cerrar.textContent = "×";
      dialogo.append(cerrar, panel);
      detalle.replaceWith(boton, dialogo);
    });

    document.querySelectorAll("[data-source-dialog]").forEach(function (boton) {
      const dialogo = boton.nextElementSibling;
      if (!dialogo || !dialogo.matches("dialog.source-dialog")) return;
      prepararDialogo(dialogo, boton.closest("tr"));
      boton.addEventListener("click", function () {
        precargarCostoEmpleado(dialogo);
        dialogo.showModal();
      });
      dialogo.querySelector(".source-dialog-close").addEventListener("click", function () { dialogo.close(); });
    });

    document.querySelectorAll('.compras-page .compras-editor-row').forEach(function (fila) {
      const celda = fila.querySelector("td");
      if (!celda) return;
      const dialogo = document.createElement("dialog");
      dialogo.className = "source-dialog";
      const cerrar = document.createElement("button");
      cerrar.type = "button";
      cerrar.className = "source-dialog-close";
      cerrar.setAttribute("aria-label", "Cerrar");
      cerrar.textContent = "×";
      const panel = document.createElement("div");
      panel.className = "source-row-panel";
      while (celda.firstChild) panel.append(celda.firstChild);
      panel.querySelectorAll("details.compras-editor").forEach(function (detalle) { detalle.open = true; });
      dialogo.append(cerrar, panel);
      document.querySelector(".compras-page").append(dialogo);
      prepararDialogo(dialogo, fila.previousElementSibling);
      cerrar.addEventListener("click", function () { dialogo.close(); });
      document.querySelectorAll('a[href="#' + fila.id + '"]').forEach(function (enlace) {
        enlace.addEventListener("click", function (evento) { evento.preventDefault(); dialogo.showModal(); });
      });
      fila.hidden = true;
    });
    document.querySelectorAll(".uat-form-editor > form, .compras-editor > form, .payable-create").forEach(function (form) {
      if (form.closest("dialog")) return;
      agregarCancelar(form, function () { form.closest("details").open = false; });
    });
  }

  function agregarCancelar(form, cerrar) {
    const botones = Array.from(form.querySelectorAll('button:not([type="button"])'));
    const guardar = botones[0];
    if (!guardar || form.querySelector(".dialog-cancel")) return;
    const acciones = document.createElement("div");
    acciones.className = "dialog-actions";
    guardar.replaceWith(acciones);
    const cancelar = document.createElement("button");
    cancelar.type = "button";
    cancelar.className = "table-action dialog-cancel";
    cancelar.textContent = "Cancelar";
    cancelar.addEventListener("click", cerrar);
    acciones.append(cancelar, ...botones);
  }

  function prepararDialogo(dialogo, fila) {
    if (!dialogo.querySelector(".payment-management-heading")) {
      const titulo = document.createElement("header");
      titulo.className = "source-dialog-heading";
      const nombre = document.createElement("h2");
      const codigo = document.createElement("small");
      nombre.textContent = fila && fila.cells[1] ? fila.cells[1].textContent.trim() : "Gestionar registro";
      codigo.textContent = fila && fila.cells[0] ? fila.cells[0].textContent.trim() : "";
      titulo.append(nombre, codigo);
      dialogo.prepend(titulo);
    }
    dialogo.querySelectorAll("form").forEach(function (form) {
      if (form.querySelector('[name="accion"][value="anular_pago_costo"]')) return;
      agregarCancelar(form, function () { dialogo.close(); });
    });
    const pie = document.createElement("div");
    pie.className = "dialog-actions dialog-footer";
    const cerrar = document.createElement("button");
    cerrar.type = "button";
    cerrar.className = "table-action";
    cerrar.textContent = "Cerrar";
    cerrar.addEventListener("click", function () { dialogo.close(); });
    pie.append(cerrar);
    dialogo.append(pie);
    dialogo.setAttribute("aria-label", dialogo.querySelector(".source-dialog-heading, .payment-management-heading").textContent.trim());
    dialogo.addEventListener("click", function (evento) {
      if (evento.target !== dialogo) return;
      const limites = dialogo.getBoundingClientRect();
      if (evento.clientX < limites.left || evento.clientX > limites.right || evento.clientY < limites.top || evento.clientY > limites.bottom) dialogo.close();
    });
  }

  function precargarCostoEmpleado(dialogo) {
    const formulario = dialogo.querySelector('form input[name="accion"][value="actualizar_costo_empleado"]');
    if (!formulario) return;
    const form = formulario.form;
    const empleadoId = form.querySelector('[name="empleado_id"]').value;
    const valores = document.querySelector('[data-employee-current="' + empleadoId + '"]');
    if (!valores) return;
    const campos = {
      sueldo_base: "sueldoBase",
      porcentaje_cargas: "porcentajeCargas",
      adicionales: "adicionales",
      otros_costos: "otrosCostos",
      horas_mensuales: "horasMensuales",
      horas_productivas: "horasProductivas"
    };
    Object.keys(campos).forEach(function (nombre) {
      const control = form.elements[nombre];
      if (control && !control.value) control.value = valores.dataset[campos[nombre]] || "";
    });
  }

  function iniciarEquiposEnBloque() {
    document.querySelectorAll("[data-team-member]").forEach(function (seleccion) {
      const fila = seleccion.closest(".resource-team-row");
      const dedicacion = fila && fila.querySelector("[data-team-dedication]");
      if (!dedicacion) return;
      function sincronizar() {
        dedicacion.disabled = !seleccion.checked;
        fila.classList.toggle("is-selected", seleccion.checked);
      }
      seleccion.addEventListener("change", sincronizar);
      sincronizar();
    });
  }

  function iniciar() {
    iniciarCriteriosDistribucion();
    iniciarPeriodicidadCostos();
    abrirDialogosDeGestion();
    iniciarEquiposEnBloque();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();

document.addEventListener("DOMContentLoaded",function(){
 const key="uat-continuar:"+location.pathname;
 document.querySelectorAll(".comercial-page form[method=post]").forEach(function(form){form.addEventListener("submit",function(event){if(event.defaultPrevented)return;const section=form.closest("section[id]");try{sessionStorage.setItem(key,JSON.stringify({y:window.scrollY,offset:section?window.scrollY-(section.getBoundingClientRect().top+window.scrollY):0,id:section?section.id:null}));}catch(_){}});});
 let saved;try{saved=JSON.parse(sessionStorage.getItem(key));sessionStorage.removeItem(key);}catch(_){}
 if(saved&&(location.search.includes("ok=")||location.search.includes("error="))){const section=saved.id&&document.getElementById(saved.id);const feedback=document.querySelector(".comercial-message,.feedback");if(section&&feedback)section.prepend(feedback);requestAnimationFrame(function(){window.scrollTo(0,section?section.getBoundingClientRect().top+window.scrollY+Math.min(saved.offset,Math.max(0,section.offsetHeight-window.innerHeight/2)):saved.y);});}
});
