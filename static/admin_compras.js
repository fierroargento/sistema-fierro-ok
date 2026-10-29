"use strict";
document.addEventListener("DOMContentLoaded", function () {
  const antiguas={'#compras-ordenes':'ordenes','#compras-recepciones':'recepciones','#compras-facturas':'facturas','#compras-proveedores':'proveedores','#compras-mapeos':'mapeos','#compras-propuestas':'propuestas'};
  const url=new URL(window.location.href),vista=antiguas[url.hash];
  if(vista&&!url.searchParams.has('vista')){url.hash='';url.searchParams.set('vista',vista);window.location.replace(url.href);return;}

  document.querySelectorAll('.compras-page a[href^="#orden-editor-"], .compras-page a[href^="#recepcion-editor-"]').forEach(function (enlace) {
    enlace.addEventListener("click", function () {
      const fila = document.getElementById(enlace.hash.slice(1));
      const editor = fila && fila.querySelector("details");
      if (editor) editor.open = true;
    });
  });
});
