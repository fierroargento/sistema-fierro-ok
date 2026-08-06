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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarBuscadorProductoMaestro);
  } else {
    iniciarBuscadorProductoMaestro();
  }
})();
