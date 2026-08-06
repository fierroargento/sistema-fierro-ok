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
    const resultado = document.getElementById("resultado-busqueda-producto");
    if (!buscador || !selector || !resultado) return;

    const productos = Array.from(selector.options).slice(1).map(function (opcion) {
      return {
        value: opcion.value,
        text: opcion.textContent,
        search: normalizar(opcion.textContent),
      };
    });
    const limite = 50;

    function mostrar(mensaje, coincidencias) {
      selector.replaceChildren(new Option(mensaje, ""));
      coincidencias.slice(0, limite).forEach(function (producto) {
        selector.add(new Option(producto.text, producto.value));
      });
    }

    function filtrar() {
      const termino = normalizar(buscador.value);
      if (termino.length < 2) {
        mostrar("Escribí para buscar", []);
        resultado.textContent = "Escribí al menos 2 caracteres.";
        return;
      }

      const coincidencias = productos.filter(function (producto) {
        return producto.search.includes(termino);
      });
      mostrar(
        coincidencias.length ? "Seleccionar producto" : "Sin coincidencias",
        coincidencias
      );
      resultado.textContent = coincidencias.length > limite
        ? "Mostrando 50 de " + coincidencias.length + " coincidencias."
        : coincidencias.length + (coincidencias.length === 1 ? " coincidencia." : " coincidencias.");
    }

    buscador.addEventListener("input", filtrar);
    filtrar();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarBuscadorProductoMaestro);
  } else {
    iniciarBuscadorProductoMaestro();
  }
})();
