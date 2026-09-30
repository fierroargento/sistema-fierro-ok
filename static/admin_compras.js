"use strict";
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll('.compras-page a[href^="#orden-editor-"], .compras-page a[href^="#recepcion-editor-"]').forEach(function (enlace) {
    enlace.addEventListener("click", function () {
      const fila = document.getElementById(enlace.hash.slice(1));
      const editor = fila && fila.querySelector("details");
      if (editor) editor.open = true;
    });
  });
});
