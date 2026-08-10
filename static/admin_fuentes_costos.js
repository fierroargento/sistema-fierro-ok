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

  function abrirDialogosDeGestion() {
    document.querySelectorAll(".source-row-action").forEach(function (detalle) {
      const panel = detalle.querySelector(":scope > .source-row-panel");
      if (!panel) return;
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "source-dialog-trigger";
      boton.setAttribute("data-source-dialog", "");
      boton.textContent = "Gestionar";
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
      boton.addEventListener("click", function () {
        precargarCostoEmpleado(dialogo);
        dialogo.showModal();
      });
      dialogo.querySelector(".source-dialog-close").addEventListener("click", function () { dialogo.close(); });
      dialogo.addEventListener("click", function (evento) {
        if (evento.target === dialogo) dialogo.close();
      });
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

  function iniciar() {
    iniciarCriteriosDistribucion();
    abrirDialogosDeGestion();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
