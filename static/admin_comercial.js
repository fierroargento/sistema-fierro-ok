(function () {
  "use strict";

  function normalizar(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function iniciarBuscadorProductoMaestro() {
    const buscador = document.getElementById("buscar-producto-maestro");
    const selector = document.getElementById("producto-maestro");
    const opciones = document.getElementById("opciones-producto-maestro");
    const resultado = document.getElementById("resultado-busqueda-producto");
    if (!buscador || !selector || !opciones || !resultado) return;

    const productos = Array.from(selector.options).slice(1).map(function (opcion) {
      return {
        value: opcion.value,
        text: opcion.textContent,
        search: normalizar(opcion.textContent),
      };
    });
    const limite = 20;
    let indiceActivo = -1;

    function botones() {
      return Array.from(opciones.querySelectorAll("button"));
    }

    function cerrar() {
      opciones.hidden = true;
      buscador.setAttribute("aria-expanded", "false");
      indiceActivo = -1;
    }

    function elegir(producto) {
      selector.value = producto.value;
      buscador.value = producto.text;
      buscador.setCustomValidity("");
      resultado.textContent = "Producto seleccionado.";
      cerrar();
    }

    function activar(indice) {
      const items = botones();
      if (!items.length) return;
      indiceActivo = (indice + items.length) % items.length;
      items.forEach(function (item, posicion) {
        item.classList.toggle("active", posicion === indiceActivo);
      });
      items[indiceActivo].scrollIntoView({ block: "nearest" });
    }

    function mostrar(coincidencias) {
      opciones.replaceChildren();
      coincidencias.slice(0, limite).forEach(function (producto) {
        const opcion = document.createElement("button");
        opcion.type = "button";
        opcion.role = "option";
        opcion.textContent = producto.text;
        opcion.addEventListener("mousedown", function (evento) {
          evento.preventDefault();
          elegir(producto);
        });
        opciones.appendChild(opcion);
      });
      opciones.hidden = coincidencias.length === 0;
      buscador.setAttribute("aria-expanded", String(coincidencias.length > 0));
      indiceActivo = -1;
    }

    function filtrar() {
      selector.value = "";
      buscador.setCustomValidity("");
      const termino = normalizar(buscador.value);
      if (termino.length < 2) {
        cerrar();
        resultado.textContent = "Escribí al menos 2 caracteres y elegí una opción.";
        return;
      }
      const coincidencias = productos.filter(function (producto) {
        return producto.search.includes(termino);
      });
      mostrar(coincidencias);
      resultado.textContent = coincidencias.length > limite
        ? "Mostrando 20 de " + coincidencias.length + " coincidencias."
        : coincidencias.length + (coincidencias.length === 1 ? " coincidencia." : " coincidencias.");
    }

    buscador.addEventListener("input", filtrar);
    buscador.addEventListener("keydown", function (evento) {
      const items = botones();
      if (evento.key === "ArrowDown" && items.length) {
        evento.preventDefault();
        activar(indiceActivo + 1);
      } else if (evento.key === "ArrowUp" && items.length) {
        evento.preventDefault();
        activar(indiceActivo - 1);
      } else if (evento.key === "Enter" && indiceActivo >= 0) {
        evento.preventDefault();
        items[indiceActivo].dispatchEvent(new MouseEvent("mousedown"));
      } else if (evento.key === "Escape") {
        cerrar();
      }
    });
    buscador.addEventListener("blur", function () {
      window.setTimeout(cerrar, 100);
    });
    buscador.form.addEventListener("submit", function (evento) {
      if (selector.value) return;
      evento.preventDefault();
      buscador.setCustomValidity("Elegí un producto de la lista.");
      buscador.reportValidity();
    });
  }

  function iniciarGestionCatalogo() {
    const buscador = document.getElementById("catalog-product-search");
    const estado = document.getElementById("catalog-state-filter");
    const disponibilidad = document.getElementById("catalog-availability-filter");
    const filas = Array.from(document.querySelectorAll("[data-catalog-row]"));

    function filtrarCatalogo() {
      const termino = normalizar(buscador && buscador.value);
      const estadoElegido = estado ? estado.value : "";
      const disponibilidadElegida = disponibilidad ? disponibilidad.value : "";
      filas.forEach(function (fila) {
        const coincideTexto = !termino || normalizar(fila.dataset.search).includes(termino);
        const coincideEstado = !estadoElegido || fila.dataset.state === estadoElegido;
        const coincideDisponibilidad = !disponibilidadElegida || fila.dataset.availability === disponibilidadElegida;
        fila.hidden = !(coincideTexto && coincideEstado && coincideDisponibilidad);
      });
    }

    [buscador, estado, disponibilidad].forEach(function (control) {
      if (control) control.addEventListener("input", filtrarCatalogo);
    });

    document.querySelectorAll("[data-open-catalog-dialog]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        const dialogo = document.getElementById(boton.dataset.openCatalogDialog);
        if (dialogo && typeof dialogo.showModal === "function") dialogo.showModal();
      });
    });
    document.querySelectorAll("[data-close-catalog-dialog]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        const dialogo = boton.closest("dialog");
        if (dialogo) dialogo.close();
      });
    });
    document.querySelectorAll(".catalog-product-dialog").forEach(function (dialogo) {
      const formulario = dialogo.querySelector(".catalog-product-form");
      const botones = Array.from(dialogo.querySelectorAll("[data-catalog-jump]"));
      const paneles = Array.from(dialogo.querySelectorAll("[data-catalog-panel]"));

      function prepararEditor(recipiente) {
        recipiente.addEventListener("click", function (evento) {
          const quitar = evento.target.closest("[data-remove-row]");
          if (!quitar) return;
          const fila = quitar.closest(".catalog-attribute-row, .catalog-variant-row");
          if (fila) fila.remove();
        });
      }

      const filasAtributos = dialogo.querySelector("[data-attribute-rows]");
      const filasVariantes = dialogo.querySelector("[data-variant-rows]");
      if (filasAtributos) prepararEditor(filasAtributos);
      if (filasVariantes) prepararEditor(filasVariantes);
      const agregarAtributo = dialogo.querySelector("[data-add-attribute]");
      if (agregarAtributo) agregarAtributo.addEventListener("click", function () {
        const plantilla = dialogo.querySelector("[data-attribute-template]");
        if (plantilla && filasAtributos) {
          filasAtributos.appendChild(plantilla.content.cloneNode(true));
          filasAtributos.lastElementChild.querySelector("input").focus();
        }
      });
      const agregarVariante = dialogo.querySelector("[data-add-variant]");
      if (agregarVariante) agregarVariante.addEventListener("click", function () {
        const plantilla = dialogo.querySelector("[data-variant-template]");
        if (plantilla && filasVariantes) {
          const vacio = filasVariantes.querySelector("[data-variant-empty]");
          if (vacio) vacio.remove();
          filasVariantes.appendChild(plantilla.content.cloneNode(true));
          filasVariantes.lastElementChild.querySelector("input").focus();
        }
      });

      function activarPestana(codigo) {
        botones.forEach(function (boton) {
          const activa = boton.dataset.catalogJump === codigo;
          boton.classList.toggle("is-active", activa);
          boton.setAttribute("aria-current", activa ? "true" : "false");
        });
      }

      function compensacionFija() {
        const cabecera = dialogo.querySelector(".catalog-dialog-head");
        const navegacion = dialogo.querySelector(".catalog-dialog-nav");
        return (cabecera ? cabecera.offsetHeight : 0) +
          (navegacion ? navegacion.offsetHeight : 0) + 8;
      }

      botones.forEach(function (boton) {
        boton.addEventListener("click", function () {
          const panel = dialogo.querySelector(
            '[data-catalog-panel="' + boton.dataset.catalogJump + '"]'
          );
          if (!panel || !formulario) return;
          activarPestana(boton.dataset.catalogJump);
          formulario.scrollTo({
            top: Math.max(0, panel.offsetTop - compensacionFija()),
            behavior: "smooth"
          });
        });
      });
      if (formulario) {
        let pendiente = false;
        formulario.addEventListener("scroll", function () {
          if (pendiente) return;
          pendiente = true;
          window.requestAnimationFrame(function () {
            const limite = formulario.getBoundingClientRect().top + compensacionFija() + 16;
            let visible = paneles[0];
            paneles.forEach(function (panel) {
              if (panel.getBoundingClientRect().top <= limite) visible = panel;
            });
            if (visible) activarPestana(visible.dataset.catalogPanel);
            pendiente = false;
          });
        }, { passive: true });
      }
      dialogo.addEventListener("close", function () {
        if (formulario) formulario.scrollTop = 0;
        activarPestana("identidad");
      });
      activarPestana("identidad");
      dialogo.addEventListener("click", function (evento) {
        if (evento.target === dialogo) dialogo.close();
      });
    });
  }

  function iniciar() {
    iniciarBuscadorProductoMaestro();
    iniciarGestionCatalogo();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
