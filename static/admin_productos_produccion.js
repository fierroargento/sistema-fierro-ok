(function () {
  "use strict";
  const form=document.getElementById("producto-form"), panel=document.getElementById("producto-fabricacion");
  if(!form || !panel)return;
  const recursos=JSON.parse(document.getElementById("productos-fabricacion-recursos").textContent);
  const grupos={insumos:{clave:"insumo_id",titulo:"Insumo",campos:[["cantidad","Cantidad","1"],["porcentaje_merma","Merma (%)","0"]]},
    operaciones:{clave:"empleado_id",titulo:"Empleado / recurso",campos:[["nombre","Operación",""],["minutos","Minutos","1"]]},
    maquinas:{clave:"maquina_id",titulo:"Máquina",campos:[["nombre","Operación",""],["minutos","Minutos","1"]]},
    fijos:{clave:"costo_fijo_id",titulo:"Costo indirecto",campos:[["porcentaje_asignacion","Asignación (%)","100"],["unidades_mensuales","Unidades / mes","1"]]}};
  let recetas=[],borradores={},unidad="",token=0,peticion=0,resultado="Pendiente de calcular",monedaSimple="ARS";
  const habilitado=!!form.elements.produccion_presentada;
  function tab(g) {
    panel.querySelectorAll("[data-fabricacion-grupo]").forEach(p=>{p.hidden=p.dataset.fabricacionGrupo!==g;});
    panel.querySelectorAll("[data-fabricacion-tab]").forEach(b=>{b.setAttribute("aria-selected",String(b.dataset.fabricacionTab===g));b.tabIndex=b.dataset.fabricacionTab===g?0:-1;});
  }
  function estado() {
    const tipo=form.elements.tipo.value,manual=tipo==="simple"||!tipo;
    panel.hidden=tipo!=="produccion";
    panel.querySelectorAll("input,select,button").forEach(c=>{c.disabled=tipo!=="produccion";});
    if(form.elements.precio_costo) {
      form.elements.precio_costo.disabled=!manual;
      if(!manual && !form.elements.moneda_costo.disabled)monedaSimple=form.elements.moneda_costo.value;
      if(manual && form.elements.moneda_costo.disabled)form.elements.moneda_costo.value=monedaSimple;
      if(!manual)form.elements.moneda_costo.value="ARS";
      form.elements.moneda_costo.disabled=!manual;
      form.querySelectorAll("[data-costo-manual]").forEach(n=>{n.hidden=!manual;});
      document.getElementById("producto-costo-titulo").textContent=manual?"Precio de costo e IVA":"IVA del producto · costo construido en ARS";
    }
    if(habilitado)filtrarRecursos();
  }
  function actual() {
    const d={unidad_id:form.elements.unidad_produccion_ui.value};
    for(const [g,cfg] of Object.entries(grupos))d[g]=Array.from(panel.querySelector('[data-fabricacion-filas="'+g+'"]').children).map(f=>{
      const v={id:f.dataset.id||null,observacion:f.dataset.observacion||""};
      f.querySelectorAll("[data-campo]").forEach(c=>{v[c.dataset.campo]=c.value;});return v;
    });
    return d;
  }
  function invalidar() {
    if(!habilitado)return;
    token++;form.elements.produccion_huella.value="";resultado="Pendiente de calcular";
    document.getElementById("producto-fabricacion-resultado").hidden=true;
    document.getElementById("producto-fabricacion-estado").textContent="Composición modificada. Calculá para ver el costo actualizado.";
  }
  function filtrarRecursos() {
    const unidadActiva=form.elements.unidad_produccion_ui.value;
    panel.querySelectorAll("select[data-campo]").forEach(s=>Array.from(s.options).forEach(o=>{
      o.disabled=!!o.value&&(o.dataset.activo==="0" || (!!o.dataset.unidad && o.dataset.unidad!==unidadActiva));
    }));
  }
  function agregar(g,d={}) {
    const cfg=grupos[g],f=document.createElement("div");f.className="producto-fabricacion-fila";f.dataset.id=d.id||"";f.dataset.observacion=d.observacion||"";
    const label=document.createElement("label"),sel=document.createElement("select");label.textContent=cfg.titulo;sel.dataset.campo=cfg.clave;sel.required=true;
    sel.add(new Option("Seleccionar "+cfg.titulo.toLowerCase(),""));
    (recursos[g]||[]).forEach(r=>{const o=new Option(r.codigo+" · "+r.nombre+" ("+r.unidad+")",String(r.id));o.dataset.unidad=String(r.unidad_id||"");o.dataset.activo=r.activo?"1":"0";sel.add(o);});
    sel.value=String(d[cfg.clave]||"");label.appendChild(sel);f.appendChild(label);
    cfg.campos.forEach(([campo,nombre,defecto])=>{const l=document.createElement("label"),c=document.createElement("input");l.textContent=nombre;c.dataset.campo=campo;c.required=true;
      if(campo==="nombre"){c.maxLength=160;c.value=d[campo]||defecto;}
      else {c.type="number";c.step="any";c.min=campo==="porcentaje_merma"?"0":"0.000001";if(campo.includes("porcentaje"))c.max="100";c.value=d[campo]===undefined?defecto:d[campo];}
      l.appendChild(c);f.appendChild(l);
    });
    sel.addEventListener("change",()=>{if(["insumos","fijos"].includes(g))f.dataset.id="";});
    const quitar=document.createElement("button");quitar.type="button";quitar.className="secondary-link";quitar.textContent="Quitar";quitar.addEventListener("click",()=>{f.remove();invalidar();});f.appendChild(quitar);
    panel.querySelector('[data-fabricacion-filas="'+g+'"]').appendChild(f);filtrarRecursos();return sel;
  }
  function cargar(d={}) {
    for(const g of Object.keys(grupos)){panel.querySelector('[data-fabricacion-filas="'+g+'"]').replaceChildren();(d[g]||[]).forEach(f=>agregar(g,f));}
    invalidar();tab("insumos");
  }
  function error(texto,control) {
    const aviso=document.getElementById("producto-fabricacion-error");aviso.hidden=false;aviso.textContent=texto;
    if(control){const g=control.closest("[data-fabricacion-grupo]");if(g)tab(g.dataset.fabricacionGrupo);control.focus();}
    return false;
  }
  if(habilitado) {
    panel.querySelectorAll("[data-fabricacion-tab]").forEach(b=>{
      b.addEventListener("click",()=>tab(b.dataset.fabricacionTab));
      b.addEventListener("keydown",e=>{if(!["ArrowLeft","ArrowRight"].includes(e.key))return;e.preventDefault();const bs=Array.from(panel.querySelectorAll("[data-fabricacion-tab]")),i=bs.indexOf(b);const destino=bs[(i+(e.key==="ArrowRight"?1:bs.length-1))%bs.length];tab(destino.dataset.fabricacionTab);destino.focus();});
    });
    panel.querySelectorAll("[data-fabricacion-agregar]").forEach(b=>b.addEventListener("click",()=>{const g=b.dataset.fabricacionAgregar;if(actual()[g].length<100){agregar(g).focus();invalidar();}}));
    panel.addEventListener("input",invalidar);
    panel.addEventListener("change",e=>{if(e.target!==form.elements.unidad_produccion_ui)invalidar();});
    form.elements.unidad_produccion_ui.addEventListener("change",()=>{
      borradores[unidad]=actual();unidad=form.elements.unidad_produccion_ui.value;
      cargar(borradores[unidad]||recetas.find(r=>String(r.unidad_id||"")===unidad)||{});filtrarRecursos();
    });
    document.getElementById("producto-fabricacion-calcular").addEventListener("click",async e=>{
      if(!window.productosProduccion.validar())return;
      const boton=e.currentTarget, datos=actual(),firma=JSON.stringify(datos),generacion=token,id=++peticion;
      const fd=new FormData();for(const [k,v] of Object.entries({_csrf_token:form.elements._csrf_token.value,tipo:"produccion",producto_id:form.elements.producto_id.value,produccion_json:firma}))fd.set(k,v);
      boton.disabled=true;boton.textContent="Calculando…";document.getElementById("producto-fabricacion-estado").textContent="Calculando materiales, tiempos y gastos…";
      try {
        const r=await fetch(boton.dataset.url,{method:"POST",body:fd,credentials:"same-origin",headers:{Accept:"application/json"}});
        let d;
        try {d=await r.json();} catch (_) {throw new Error("No se pudo leer el cálculo. Revisá tu sesión e intentá de nuevo.");}
        if(generacion!==token||firma!==JSON.stringify(actual()))return;
        if(!r.ok)throw new Error(d.error||"No se pudo calcular.");
        form.elements.produccion_huella.value=d.huella;
        const destino=document.getElementById("producto-fabricacion-resultado");destino.replaceChildren();
        const formato=n=>(Number(n)/100).toLocaleString("es-AR",{style:"currency",currency:"ARS"});
        const lista=document.createElement("ul");(d.detalles||[]).forEach(f=>{const li=document.createElement("li");li.textContent=f.concepto+" · "+f.cantidad+" "+f.unidad_medida+" · "+formato(f.subtotal_centavos);lista.appendChild(li);});
        const total=document.createElement("strong");resultado=formato(d.total_centavos)+" por unidad de medida del producto";total.textContent="Costo unitario: "+resultado;destino.append(lista,total);destino.hidden=false;
        document.getElementById("producto-fabricacion-estado").textContent="Cálculo terminado. Todavía no se guardó ningún cambio.";
      } catch(err) {
        if(generacion===token){error(err instanceof TypeError ? "No se pudo conectar para calcular. Intentá de nuevo." : err.message);resultado="Costo pendiente";document.getElementById("producto-fabricacion-estado").textContent="Costo pendiente. Revisá los datos o las tarifas indicadas.";}
      } finally {if(id===peticion){boton.disabled=form.elements.tipo.value!=="produccion";boton.textContent="Calcular costo unitario";}}
    });
  }
  form.elements.tipo.addEventListener("change",()=>{invalidar();estado();});
  window.productosProduccion={
    abrir(fila,fallido) {
      token++;peticion++;monedaSimple=form.elements.moneda_costo?form.elements.moneda_costo.value:"ARS";
      if(habilitado){recetas=(fila&&fila.producciones)||[];borradores={};let d=null;
        if(fallido){try{d=JSON.parse(fallido.produccion_json||"null");}catch(_){d=null;}}
        const inicial=d||recetas.find(r=>!r.unidad_id)||recetas[0]||{};unidad=String(inicial.unidad_id||"");form.elements.unidad_produccion_ui.value=unidad;cargar(inicial);
        document.getElementById("producto-fabricacion-error").hidden=true;form.elements.produccion_huella.value="";
        document.getElementById("producto-fabricacion-calcular").textContent="Calcular costo unitario";
      }estado();
    },
    mostrarError(c){const g=c.closest("[data-fabricacion-grupo]");if(g)tab(g.dataset.fabricacionGrupo);},
    validar() {
      if(form.elements.tipo.value!=="produccion")return true;
      if(!habilitado)return false;
      document.getElementById("producto-fabricacion-error").hidden=true;
      const d=actual();if(!Object.keys(grupos).some(g=>d[g].length))return error("Agregá lo necesario para fabricar el producto: insumos, operaciones o recursos.");
      for(const c of panel.querySelectorAll("input[data-campo],select[data-campo]")) {
        if(!c.validity.valid || (c.tagName==="SELECT" && c.selectedOptions[0]&&c.selectedOptions[0].disabled))return error("Revisá los recursos, cantidades y tiempos de fabricación.",c);
      }
      form.elements.produccion_json.value=JSON.stringify(d);return true;
    },
    resumen(){return resultado;}
  };
})();
