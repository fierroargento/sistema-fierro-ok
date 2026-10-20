(function () {
  "use strict";
  const form = document.getElementById("producto-form");
  if (!form || !form.elements.datos_generales_presentados) return;
  const configuracion = JSON.parse(document.getElementById("productos-clasificaciones").textContent);
  const proveedores = document.getElementById("producto-proveedores-filas");
  const barras = document.getElementById("producto-barras-filas");
  const fotos = document.getElementById("producto-imagenes");
  let guardadas = [], nuevas = [], principal = "";
  const error = document.getElementById("producto-adicional-error");
  const campoDefinido = campo => campo === "depositos" ? "depositos_definidos" : "sucursales_definidas";
  const parser = (valor, defecto) => { try { return JSON.parse(valor); } catch (_) { return defecto; } };
  function avisar(texto, paso) {
    if (paso) form.dispatchEvent(new CustomEvent("producto-error-paso", {detail:paso}));
    error.textContent = texto; error.hidden = false;
    error.scrollIntoView({block:"nearest"}); return false;
  }
  function agregarProveedor(dato) {
    const fila = document.getElementById("producto-proveedor-template").content.firstElementChild.cloneNode(true);
    const selector = fila.querySelector("[data-proveedor]");
    const id = dato ? String(dato.proveedor_id) : "";
    Array.from(selector.options).forEach(o => { o.disabled = o.dataset.activo === "0" && o.value !== id; });
    selector.value = id;
    fila.querySelector("[data-codigo-proveedor]").value = dato ? dato.codigo : "";
    fila.querySelector("[data-quitar-proveedor]").addEventListener("click", () => fila.remove());
    proveedores.appendChild(fila);
    return selector;
  }
  function agregarBarra(codigo) {
    const fila = document.getElementById("producto-barra-template").content.firstElementChild.cloneNode(true);
    fila.querySelector("[data-codigo-barras]").value = codigo || "";
    fila.querySelector("[data-quitar-barra]").addEventListener("click", () => fila.remove());
    barras.appendChild(fila);return fila.querySelector("[data-codigo-barras]");
  }
  function ubicaciones(campo) {
    const definida = form.elements[campoDefinido(campo)].checked;
    document.querySelectorAll('[data-ubicaciones="' + campo + '"] input').forEach(c => {
      c.disabled = !definida || (c.dataset.activa === "0" && !c.checked);
    });
  }
  function clasificaciones() {
    const rubros = [...new Set(configuracion.map(c=>c.rubro).filter(Boolean))];
    const marcas = [...new Set(configuracion.map(c=>c.marca).filter(Boolean))];
    const subrubros = [...new Set(configuracion.filter(c=>c.rubro.toLocaleLowerCase()===form.elements.rubro.value.trim().toLocaleLowerCase()).map(c=>c.subrubro).filter(Boolean))];
    for (const [id,valores] of [["producto-rubros",rubros],["producto-marcas",marcas],["producto-subrubros",subrubros]]) {
      const destino=document.getElementById(id);destino.replaceChildren();
      valores.sort().forEach(v=>{const o=document.createElement("option");o.value=v;destino.appendChild(o);});
    }
    form.elements.subrubro.disabled = !form.elements.rubro.value.trim();
  }
  function ejemploUtilidad() {
    const texto=form.elements.utilidad_pct.value.trim();
    const pct=Number(texto.replace(",","."));
    const destino=document.getElementById("producto-utilidad-ejemplo");
    if (!texto) { destino.textContent="Sin objetivo definido. Dejar vacío conserva ese estado; cero es un objetivo explícito.";return; }
    const venta=form.elements.utilidad_base.value === "precio_venta";
    if (!Number.isFinite(pct)||pct<0||(venta&&pct>=100)) {destino.textContent="Revisá el porcentaje; sobre precio de venta debe ser menor al 100%.";return;}
    const precio=venta?100/(1-pct/100):100*(1+pct/100);
    destino.textContent="Ejemplo sin gastos ni impuestos: costo $100 → precio $"+(Math.ceil(precio*100)/100).toLocaleString("es-AR",{minimumFractionDigits:2,maximumFractionDigits:2})+". Es una referencia, no un precio de publicación.";
  }
  function ejemploCosto() {
    const costo=form.elements.precio_costo.value.trim(), iva=form.elements.iva_pct.value.trim();
    const moneda=form.elements.moneda_costo.value;
    const importe=Number(costo.replace(",", ".")), tasa=Number(iva.replace(",", "."));
    const destino=document.getElementById("producto-costo-ejemplo");
    if (!costo) {destino.textContent="Costo sin definir. Podés completarlo más adelante.";return;}
    if (!Number.isFinite(importe)||importe<0||importe>999999999999.99||!Number.isFinite(tasa)||tasa<0||tasa>100) {
      destino.textContent="Revisá el costo y el porcentaje de IVA.";return;
    }
    const formato=n=>n.toLocaleString("es-AR",{style:"currency",currency:moneda,currencyDisplay:"code"});
    destino.textContent=iva ? "Sin IVA: "+formato(importe)+" · IVA: "+formato(importe*tasa/100)+" · Con IVA: "+formato(importe*(1+tasa/100)) :
      "Costo sin IVA: "+formato(importe)+" · IVA sin definir; no se calcula el total con IVA.";
  }
  function renderFotos() {
    fotos.replaceChildren();
    const filas=guardadas.map(f=>({...f,clave:String(f.id)})).concat(nuevas.map((f,n)=>({clave:"nueva:"+n,nombre:f.name,archivo:f})));
    if (!filas.some(f=>f.clave===principal)) principal=filas.length?filas[0].clave:"";
    filas.forEach(f=>{
      const tarjeta=document.createElement("div");tarjeta.className="producto-imagen";
      const imagen=document.createElement("img");imagen.alt=f.nombre;
      if (f.archivo) {const lector=new FileReader();lector.onload=()=>{imagen.src=lector.result;};lector.readAsDataURL(f.archivo);} else imagen.src=f.url;
      const etiqueta=document.createElement("label");
      const radio=document.createElement("input");radio.type="radio";radio.name="producto-foto-principal-ui";radio.value=f.clave;radio.checked=f.clave===principal;
      radio.addEventListener("change",()=>{principal=f.clave;});etiqueta.append(radio,document.createTextNode("Principal"));
      const nombre=document.createElement("span");nombre.textContent=f.nombre;nombre.title=f.nombre;
      const quitar=document.createElement("button");quitar.type="button";quitar.className="secondary-link";quitar.textContent="Quitar";
      quitar.addEventListener("click",()=>{
        if (f.archivo) {
          const n=Number(f.clave.split(":")[1]);nuevas.splice(n,1);
          if (principal.startsWith("nueva:")) {const p=Number(principal.split(":")[1]);principal=p===n?"":p>n?"nueva:"+(p-1):principal;}
        } else guardadas=guardadas.filter(g=>String(g.id)!==f.clave);
        renderFotos();
      });
      tarjeta.append(imagen,nombre,etiqueta,quitar);fotos.appendChild(tarjeta);
    });
    // El archivo se envía solo al confirmar el guardado, junto con la ficha.
    const transferencia=new DataTransfer();nuevas.forEach(f=>transferencia.items.add(f));
    form.elements.imagenes_producto.files=transferencia.files;
  }
  form.elements.imagenes_producto.addEventListener("change",e=>{
    error.hidden=true;
    const archivos=Array.from(e.target.files);
    if (guardadas.length+nuevas.length+archivos.length>5||archivos.some(f=>f.size>2*1024*1024||!/[.](jpe?g|png|webp)$/i.test(f.name))) {
      renderFotos();avisar("Usá hasta 5 imágenes JPG, PNG o WEBP, de hasta 2 MB cada una.", "imagenes");return;
    }
    nuevas=nuevas.concat(archivos);renderFotos();
  });
  document.getElementById("producto-proveedor-agregar").addEventListener("click",()=>{if(proveedores.children.length<20)agregarProveedor(null).focus();});
  document.getElementById("producto-barra-agregar").addEventListener("click",()=>{if(barras.children.length<20)agregarBarra("").focus();});
  for(const campo of ["sucursales","depositos"]) form.elements[campoDefinido(campo)].addEventListener("change",()=>ubicaciones(campo));
  form.elements.rubro.addEventListener("input",clasificaciones);
  form.elements.utilidad_pct.addEventListener("input",ejemploUtilidad);
  form.elements.utilidad_base.addEventListener("change",ejemploUtilidad);
  for (const campo of ["precio_costo", "iva_pct", "moneda_costo"]) {
    form.elements[campo].addEventListener("input", ejemploCosto);
    form.elements[campo].addEventListener("change", ejemploCosto);
  }
  window.productosDatos = {
    abrir(fila, fallido) {
      const d=fallido || (fila && fila.adicionales) || {};
      error.hidden=true;proveedores.replaceChildren();barras.replaceChildren();
      for(const campo of ["rubro","subrubro","marca","utilidad_pct","precio_costo","iva_pct"]) form.elements[campo].value=d[campo]||"";
      form.elements.utilidad_base.value=d.utilidad_base||"costo";
      form.elements.moneda_costo.value=d.moneda_costo||"ARS";
      const prov=fallido?parser(d.proveedores_json,[]):(d.proveedores||[]);prov.forEach(agregarProveedor);
      const codigos=fallido?parser(d.codigos_barras_json,[]):(d.codigos_barras||[]);codigos.forEach(agregarBarra);
      for(const campo of ["sucursales","depositos"]) {
        form.elements[campoDefinido(campo)].checked=fallido?d[campoDefinido(campo)]==="1":!!d[campoDefinido(campo)];
        const ids=fallido?parser(d[campo+"_json"],[]):(d[campo]||[]);
        document.querySelectorAll('[data-ubicaciones="'+campo+'"] input').forEach(c=>{c.checked=ids.map(String).includes(c.value);});
        ubicaciones(campo);
      }
      const actuales=(fila && fila.adicionales && fila.adicionales.imagenes)||[];
      const conservar=fallido?parser(d.imagenes_conservar_json,[]):actuales.map(f=>f.id);
      guardadas=actuales.filter(f=>conservar.map(String).includes(String(f.id)));nuevas=[];
      principal=fallido?d.imagen_principal:(String((guardadas.find(f=>f.principal)||{}).id||""));
      const aviso=document.getElementById("producto-fotos-aviso");aviso.hidden=!(fallido&&Number(d.imagenes_nuevas_cantidad)>0);
      aviso.textContent="Volvé a seleccionar las fotos nuevas: el guardado fue rechazado y no se cargaron.";
      renderFotos();clasificaciones();ejemploUtilidad();ejemploCosto();
    },
    validar(paso) {
      error.hidden=true;
      const prov=Array.from(proveedores.children).map(f=>({proveedor_id:f.querySelector("[data-proveedor]").value,codigo:f.querySelector("[data-codigo-proveedor]").value}));
      if((!paso || paso === "comercial") && new Set(prov.map(p=>p.proveedor_id)).size!==prov.length)return avisar("El proveedor está repetido. Conservá una fila por proveedor.", "comercial");
      const codigos=Array.from(barras.children).map(f=>f.querySelector("[data-codigo-barras]").value.trim());
      if((!paso || paso === "imagenes") && new Set(codigos).size!==codigos.length)return avisar("Hay códigos de barras repetidos.", "imagenes");
      if((!paso || paso === "comercial") && form.elements.subrubro.value.trim()&&!form.elements.rubro.value.trim())return avisar("Elegí el rubro del subrubro.", "comercial");
      if(!paso || paso === "costos") {
        for (const [campo, nombre, maximo, decimales] of [["precio_costo","Precio de costo",999999999999.99,2],["iva_pct","IVA",100,6]]) {
          if (form.elements[campo].disabled) continue;
          const texto=form.elements[campo].value.trim().replace(",", ".");
          const valor=Number(texto);
          const patron=new RegExp("^(?:\\d+(?:\\.\\d{1,"+decimales+"})?|\\.\\d{1,"+decimales+"})$");
          if(texto && (!patron.test(texto)||!Number.isFinite(valor)||valor<0||valor>maximo))
            return avisar(nombre+": revisá el valor. Usá hasta "+decimales+" decimales, sin separadores de miles.", "costos");
        }
        if(!["ARS","USD"].includes(form.elements.moneda_costo.value)) return avisar("Elegí Pesos (ARS) o Dólares (USD).", "costos");
        const texto=form.elements.utilidad_pct.value.trim(), numero=Number(texto.replace(",", "."));
        if(texto && (!/^(?:\d+(?:[.,]\d{1,6})?|[.,]\d{1,6})$/.test(texto) || !Number.isFinite(numero) || numero<0 || numero>999999.999999 || (form.elements.utilidad_base.value==="precio_venta" && numero>=100)))
          return avisar("Revisá la utilidad: usá un porcentaje positivo o cero, con hasta seis decimales. Sobre precio de venta debe ser menor al 100%.", "costos");
      }
      form.elements.proveedores_json.value=JSON.stringify(prov);
      form.elements.codigos_barras_json.value=JSON.stringify(codigos);
      for(const campo of ["sucursales","depositos"])form.elements[campo+"_json"].value=JSON.stringify(Array.from(document.querySelectorAll('[data-ubicaciones="'+campo+'"] input:checked')).map(c=>Number(c.value)));
      form.elements.imagenes_conservar_json.value=JSON.stringify(guardadas.map(f=>f.id));
      form.elements.imagen_principal.value=principal;
      form.elements.imagenes_nuevas_cantidad.value=String(nuevas.length);
      return true;
    }
  };
})();
