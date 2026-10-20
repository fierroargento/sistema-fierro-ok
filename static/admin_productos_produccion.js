(function () {
  "use strict";
  const form=document.getElementById("producto-form"), panel=document.getElementById("producto-fabricacion");
  if(!form || !panel)return;
  const recursos=JSON.parse(document.getElementById("productos-fabricacion-recursos").textContent);
  const grupos={maquinas:{clave:"maquina_id",titulo:"Máquina",campos:[["nombre","Operación",""],["minutos","Minutos","1"]]},
    fijos:{clave:"costo_fijo_id",titulo:"Costo indirecto",campos:[["porcentaje_asignacion","Asignación (%)","100"],["unidades_mensuales","Unidades / mes","1"]]}};
  let piezas=[],tareas=[],editorIndice=null;
  let recetas=[],borradores={},unidad="",token=0,peticion=0,resultado="Pendiente de calcular",monedaSimple="ARS";
  const habilitado=!!form.elements.produccion_presentada;
  const piezaDialog=document.getElementById("producto-pieza-dialog"), tareaDialog=document.getElementById("producto-tarea-dialog");
  const piezaForm=document.getElementById("producto-pieza-form"), tareaForm=document.getElementById("producto-tarea-form");
  const listaRecursos=(g)=>(recursos[g]||[]).filter(r=>r.activo&&(!r.unidad_id||String(r.unidad_id)===form.elements.unidad_produccion_ui.value));
  const material=id=>(recursos.insumos||[]).find(r=>String(r.id)===String(id));
  const numero=n=>Number(String(n||0).replace(",","."));
  const formato=n=>Number(n).toLocaleString("es-AR",{maximumFractionDigits:6});
  function consumo(p) {return p.modo==="longitud" ? numero(p.cantidad)*numero(p.largo_cm)/100 : p.modo==="rendimiento" ? numero(p.cantidad)/numero(p.rendimiento) : numero(p.cantidad);}
  function llenarSelector(s,g,valor) {
    s.replaceChildren(new Option("Seleccionar", ""));
    listaRecursos(g).forEach(r=>s.add(new Option(r.codigo+" · "+r.nombre,String(r.id))));
    if(valor&&!Array.from(s.options).some(o=>o.value===String(valor))){const o=new Option("Revisar recurso "+valor,String(valor));o.disabled=true;s.add(o);}
    s.value=String(valor||"");
  }
  const buscarMaterial=document.getElementById("pieza-material-buscar");
  const nombrePieza=piezaForm&&piezaForm.elements.nombre;
  const normalizarBusqueda=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
  function etiquetasMaterial(r) {
    const partes=["Insumo: "+r.codigo];
    if((r.skus||[]).length)partes.push("SKU: "+r.skus.join(", "));
    (r.codigos_proveedor||[]).forEach(p=>partes.push(p.codigo+" · "+p.proveedor));
    if((r.proveedores||[]).length)partes.push(r.proveedores.join(" / "));
    partes.push(r.unidad);return partes.join(" | ");
  }
  function seleccionMaterial(r,desdeNombre=false) {
    piezaForm.elements.insumo_id.value=String(r.id);
    buscarMaterial.value=r.nombre+" · "+r.codigo;
    buscarMaterial.setCustomValidity("");
    if(desdeNombre||!nombrePieza.value.trim())nombrePieza.value=r.nombre;
    nombrePieza.setCustomValidity(nombrePieza.value.length>160?"Usá un nombre de pieza de hasta 160 caracteres.":"");
    piezaForm.elements.insumo_id.dispatchEvent(new Event("change",{bubbles:true}));
  }
  function coincidenciasMateriales(disponibles,consulta) {
    const terminos=consulta.split(/\s+/).filter(Boolean);
    const exactos=consulta?disponibles.filter(r=>[r.codigo,...(r.skus||[]),...(r.codigos_proveedor||[]).map(p=>p.codigo)].some(c=>normalizarBusqueda(c)===consulta)):[];
    return exactos.length?exactos:disponibles.filter(r=>{const texto=normalizarBusqueda(r.nombre+" "+etiquetasMaterial(r));return terminos.every(t=>texto.includes(t));});
  }
  function sinCoincidencias(consulta,esNombre) {
    if(esNombre)return "Sin coincidencias. Podés conservar este nombre propio para la pieza.";
    const selector=form.elements.unidad_produccion_ui, actual=selector.selectedOptions[0]?.textContent||"General";
    const otras=coincidenciasMateriales((recursos.insumos||[]).filter(r=>r.activo&&r.unidad_id&&String(r.unidad_id)!==selector.value),consulta);
    const unidades=Array.from(new Set(otras.map(r=>Array.from(selector.options).find(o=>o.value===String(r.unidad_id)&&o.dataset.activa!=="0")?.textContent).filter(Boolean)));
    if(unidades.length)return "El insumo coincide en "+unidades.join(" / ")+". En Unidad de fabricación elegiste "+actual+". Cerrá este cuadro y elegí la unidad correspondiente para usarlo.";
    const inactivos=coincidenciasMateriales((recursos.insumos||[]).filter(r=>!r.activo&&(!r.unidad_id||String(r.unidad_id)===selector.value)),consulta);
    if(inactivos.length)return "Hay coincidencias con insumos inactivos. Revisá su estado en Insumos y precios antes de usarlos.";
    return "Sin coincidencias entre los insumos activos de "+actual+". Revisá el código o la unidad de fabricación.";
  }
  function autocompletar(input,lista,elegir) {
    let opciones=[],indice=-1;
    function cerrar(){lista.hidden=true;input.setAttribute("aria-expanded","false");input.removeAttribute("aria-activedescendant");indice=-1;}
    function activar(n){indice=n;Array.from(lista.querySelectorAll("[role=option]")).forEach((b,i)=>b.setAttribute("aria-selected",String(i===n)));const b=lista.querySelectorAll("[role=option]")[n];if(b){input.setAttribute("aria-activedescendant",b.id);b.scrollIntoView({block:"nearest"});}}
    function mostrar(){
      if(input===nombrePieza&&!input.value.trim()){cerrar();return;}
      const consulta=normalizarBusqueda(input.value);
      const coincidencias=coincidenciasMateriales(listaRecursos("insumos"),consulta);
      opciones=coincidencias.slice(0,8);indice=-1;lista.replaceChildren();
      opciones.forEach((r,i)=>{const boton=document.createElement("button");boton.type="button";boton.id=lista.id+"-"+i;boton.setAttribute("role","option");boton.setAttribute("aria-selected","false");boton.tabIndex=-1;
        const nombre=document.createElement("strong"),detalle=document.createElement("span");nombre.textContent=r.nombre;detalle.textContent=etiquetasMaterial(r);boton.append(nombre,detalle);
        boton.addEventListener("mousedown",e=>e.preventDefault());boton.addEventListener("click",()=>{elegir(r);cerrar();input.focus();});lista.appendChild(boton);});
      const aviso=document.createElement("p");aviso.className="pieza-busqueda-aviso";aviso.textContent=!opciones.length?sinCoincidencias(consulta,input===nombrePieza):coincidencias.length>8?"Mostrando 8 de "+coincidencias.length+". Escribí más datos para precisar la búsqueda.":coincidencias.length+" resultado(s). Elegí el que corresponde.";lista.appendChild(aviso);
      lista.hidden=false;input.setAttribute("aria-expanded","true");input.removeAttribute("aria-activedescendant");
    }
    input.addEventListener("input",mostrar);input.addEventListener("focus",mostrar);
    input.addEventListener("blur",()=>setTimeout(cerrar,100));
    input.addEventListener("keydown",e=>{
      if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();e.stopPropagation();if(lista.hidden)mostrar();if(opciones.length)activar((indice+(e.key==="ArrowDown"?1:opciones.length-1)+opciones.length)%opciones.length);}
      if(e.key==="Enter"&&!lista.hidden&&indice>=0){e.preventDefault();e.stopPropagation();elegir(opciones[indice]);cerrar();}
      if(e.key==="Escape"&&!lista.hidden){e.preventDefault();e.stopPropagation();cerrar();}
    });
    return {cerrar};
  }
  let sugerenciasNombre=null,sugerenciasMaterial=null;
  if(habilitado&&buscarMaterial){
    sugerenciasNombre=autocompletar(nombrePieza,document.getElementById("pieza-nombre-opciones"),r=>seleccionMaterial(r,true));
    sugerenciasMaterial=autocompletar(buscarMaterial,document.getElementById("pieza-material-opciones"),r=>seleccionMaterial(r));
    buscarMaterial.addEventListener("input",()=>{piezaForm.elements.insumo_id.value="";buscarMaterial.setCustomValidity("Elegí un material de los resultados.");prepararPieza();});
    nombrePieza.addEventListener("input",()=>nombrePieza.setCustomValidity(nombrePieza.value.length>160?"Usá un nombre de pieza de hasta 160 caracteres.":""));
    piezaDialog.addEventListener("close",()=>{sugerenciasNombre.cerrar();sugerenciasMaterial.cerrar();});
  }

  function resumenConsumos() {
    const destino=document.getElementById("producto-consumos-resumen");destino.replaceChildren();const consumos=new Map();
    piezas.forEach(p=>consumos.set(String(p.insumo_id),(consumos.get(String(p.insumo_id))||0)+consumo(p)));
    const ul=document.createElement("ul");consumos.forEach((q,id)=>{const li=document.createElement("li"),m=material(id);li.textContent=(m?m.nombre:"Revisar material")+": "+formato(q)+" "+(m?m.unidad:"");ul.appendChild(li);});destino.appendChild(ul);
    const seg=tareas.reduce((a,t)=>a+numero(t.segundos),0);document.getElementById("producto-tiempo-resumen").textContent="Tiempo total: "+formato(seg)+" segundos ("+formato(seg/60)+" minutos) por unidad fabricada.";
  }
  function renderListas() {
    for(const [g,datos] of [["piezas",piezas],["tareas",tareas]]){
      const lista=document.getElementById(g==="piezas"?"producto-piezas-lista":"producto-tareas-lista");lista.replaceChildren();
      if(!datos.length){const p=document.createElement("p");p.className="productos-muted";p.textContent=g==="piezas"?"Todavía no agregaste componentes.":"Todavía no agregaste tareas.";lista.appendChild(p);}
      datos.forEach((r,i)=>{const fila=document.createElement("div");fila.className="producto-despiece-fila";const texto=document.createElement("div"),nombre=document.createElement("strong"),detalle=document.createElement("small");nombre.textContent=r.nombre;
        if(g==="piezas"){const m=material(r.insumo_id);detalle.textContent=(m?m.nombre:"Revisar material")+" · "+formato(r.cantidad)+(r.modo==="longitud"?" × "+formato(r.largo_cm)+" cm":r.modo==="rendimiento"?" / "+formato(r.rendimiento)+" piezas por unidad":"")+" → "+formato(consumo(r))+" "+(m?m.unidad:"");}
        else detalle.textContent=formato(r.segundos)+" segundos por unidad";
        texto.append(nombre,detalle);const acciones=document.createElement("div");acciones.className="productos-actions";
        const editar=document.createElement("button");editar.type="button";editar.className="secondary-link";editar.textContent="Editar";editar.dataset.fierroIcon="gestionar";editar.addEventListener("click",()=>g==="piezas"?abrirPieza(i):abrirTarea(i));
        const quitar=document.createElement("button");quitar.type="button";quitar.className="secondary-link";quitar.textContent="Quitar";quitar.addEventListener("click",()=>{datos.splice(i,1);renderListas();invalidar();});acciones.append(editar,quitar);fila.append(texto,acciones);lista.appendChild(fila);
      });
    }resumenConsumos();
  }
  function prepararPieza() {
    document.getElementById("pieza-unidad-fabricacion").textContent=form.elements.unidad_produccion_ui.selectedOptions[0]?.textContent||"General";
    const m=material(piezaForm.elements.insumo_id.value),modo=piezaForm.elements.modo.value;
    document.getElementById("pieza-unidad").textContent=m?m.unidad:"Seleccioná un material";
    document.getElementById("pieza-medida-label").hidden=modo!=="longitud";piezaForm.elements.largo_cm.disabled=modo!=="longitud";
    document.getElementById("pieza-rendimiento-label").hidden=modo!=="rendimiento";piezaForm.elements.rendimiento.disabled=modo!=="rendimiento";
    const p=Object.fromEntries(new FormData(piezaForm));const q=consumo(p);
    document.getElementById("pieza-consumo-preview").textContent=m&&Number.isFinite(q)&&q>0?"Consumo por producto: "+formato(q)+" "+m.unidad:"Completá los datos para ver el consumo.";
  }
  function abrirPieza(i=null) {
    editorIndice=i;piezaForm.querySelectorAll('[type="submit"]').forEach(b=>b.disabled=i===null&&piezas.length>=100);piezaForm.reset();piezaForm.querySelector("[data-editor-feedback]").hidden=true;sugerenciasNombre.cerrar();sugerenciasMaterial.cerrar();buscarMaterial.setCustomValidity("");nombrePieza.setCustomValidity("");llenarSelector(piezaForm.elements.insumo_id,"insumos",i===null?"":piezas[i].insumo_id);
    const d=i===null?{modo:"directo",cantidad:"1"}:piezas[i];for(const [k,v] of Object.entries(d))if(piezaForm.elements[k])piezaForm.elements[k].value=v;
    const seleccionado=material(piezaForm.elements.insumo_id.value);buscarMaterial.value=seleccionado?seleccionado.nombre+" · "+seleccionado.codigo:"";
    buscarMaterial.setCustomValidity(seleccionado?"":"Elegí un material de los resultados.");
    piezaForm.querySelector("[data-editor-guardar]").textContent=i===null?"Agregar componente":"Aplicar cambios";prepararPieza();if(!piezaDialog.open)piezaDialog.showModal();buscarMaterial.focus();
  }
  function abrirTarea(i=null) {
    editorIndice=i;tareaForm.querySelectorAll('[type="submit"]').forEach(b=>b.disabled=i===null&&tareas.length>=100);tareaForm.reset();tareaForm.querySelector("[data-editor-feedback]").hidden=true;if(i!==null){tareaForm.elements.nombre.value=tareas[i].nombre;tareaForm.elements.tiempo.value=tareas[i].segundos;}
    tareaForm.querySelector("[data-editor-guardar]").textContent=i===null?"Agregar tarea":"Aplicar cambios";if(!tareaDialog.open)tareaDialog.showModal();tareaForm.elements.nombre.focus();
  }

  function finalizarEditor(e,grupo) {
    const esPieza=grupo==="piezas",dlg=esPieza?piezaDialog:tareaDialog,f=esPieza?piezaForm:tareaForm;
    const cantidad=esPieza?piezas.length:tareas.length,editando=editorIndice!==null;
    if(e.submitter&&e.submitter.hasAttribute("data-editor-otra")) {
      const unidadTiempo=esPieza?null:f.elements.unidad.value;
      if(esPieza)abrirPieza();else {abrirTarea();f.elements.unidad.value=unidadTiempo;}
      const aviso=f.querySelector("[data-editor-feedback]");aviso.hidden=false;
      aviso.textContent=(editando?"Cambios aplicados a la ficha. ":esPieza?"Componente agregado a la ficha. ":"Tarea agregada a la ficha. ")+(cantidad<100?"Cargá "+(esPieza?"el siguiente.":"la siguiente."):"Llegaste al máximo de 100 filas. Cerrá este cuadro para continuar.");
      f.querySelectorAll('[type="submit"]').forEach(b=>{b.disabled=cantidad>=100;});
    } else dlg.close();
  }
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
    const d={unidad_id:form.elements.unidad_produccion_ui.value,piezas:piezas.map(p=>({...p})),tareas:tareas.map(t=>({...t})),tarifa_id:form.elements.tarifa_produccion_ui.value};
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
    const estado=d.despiece, fisico=estado&&estado.actual?estado.datos:d;
    piezas=(fisico.piezas||(d.insumos||[]).map(r=>({nombre:"Consumo previo · "+((material(r.insumo_id)||{}).nombre||"material"),insumo_id:r.insumo_id,cantidad:String(Math.round(numero(r.cantidad)*(1+numero(r.porcentaje_merma)/100)*1e6)/1e6),modo:"directo",largo_cm:"",rendimiento:""}))).map(p=>({...p}));
    tareas=(fisico.tareas||(d.operaciones||[]).map(r=>({nombre:r.nombre,segundos:String(numero(r.minutos)*60)}))).map(t=>({...t}));
    const tarifasPrevias=new Set((d.operaciones||[]).map(r=>String(r.empleado_id)));
    let tarifa=fisico.tarifa_id||(tarifasPrevias.size===1?((d.operaciones||[])[0]||{}).empleado_id:"")||"";
    llenarSelector(form.elements.tarifa_produccion_ui,"operaciones",tarifa);
    const opciones=listaRecursos("operaciones");if(!tarifa&&tarifasPrevias.size<2&&opciones.length===1)form.elements.tarifa_produccion_ui.value=String(opciones[0].id);
    for(const g of Object.keys(grupos)){panel.querySelector('[data-fabricacion-filas="'+g+'"]').replaceChildren();(d[g]||[]).forEach(f=>agregar(g,f));}
    renderListas();invalidar();tab("piezas");
    const aviso=document.getElementById("producto-fabricacion-error");aviso.hidden=true;
    if(estado&&!estado.actual)error("La composición cambió desde Costos. Se muestran sus consumos actuales; revisá las piezas y tareas antes de guardar.");
    if(tarifasPrevias.size>1&&!fisico.tarifa_id)error("La composición anterior utiliza varias tarifas. Elegí la tarifa del taller y revisá las tareas antes de guardar.");
  }
  function error(texto,control) {
    const aviso=document.getElementById("producto-fabricacion-error");aviso.hidden=false;aviso.textContent=texto;
    if(control){const g=control.closest("[data-fabricacion-grupo]");if(g)tab(g.dataset.fabricacionGrupo);control.focus();}
    return false;
  }
  if(habilitado) {
    document.getElementById("producto-pieza-agregar").addEventListener("click",()=>{if(piezas.length<100)abrirPieza();});
    document.getElementById("producto-tarea-agregar").addEventListener("click",()=>{if(tareas.length<100)abrirTarea();});
    for(const [dlg,f] of [[piezaDialog,piezaForm],[tareaDialog,tareaForm]]){
      f.querySelector("[data-editor-cancelar]").addEventListener("click",()=>dlg.close());
      f.addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.tagName!=="BUTTON")e.preventDefault();});
    }
    piezaForm.addEventListener("input",prepararPieza);
    piezaForm.elements.insumo_id.addEventListener("change",()=>{const m=material(piezaForm.elements.insumo_id.value);buscarMaterial.value=m?m.nombre+" · "+m.codigo:"";buscarMaterial.setCustomValidity(m?"":"Elegí un material de los resultados.");piezaForm.elements.modo.value=m&&["m","metro","metros"].includes(m.unidad.toLowerCase().trim())?"longitud":"directo";prepararPieza();});
    piezaForm.elements.modo.addEventListener("change",prepararPieza);
    piezaForm.addEventListener("submit",e=>{e.preventDefault();if(editorIndice===null&&piezas.length>=100)return;if(!piezaForm.reportValidity())return;const p=Object.fromEntries(new FormData(piezaForm));const m=material(p.insumo_id);
      if(!m||!Number.isFinite(consumo(p))||consumo(p)<=0)return;
      if(p.modo==="longitud"&&!["m","metro","metros"].includes(m.unidad.toLowerCase().trim())){piezaForm.elements.modo.setCustomValidity("Este material no está cotizado por metro.");piezaForm.elements.modo.reportValidity();piezaForm.elements.modo.setCustomValidity("");return;}
      if(editorIndice===null)piezas.push(p);else piezas[editorIndice]=p;renderListas();invalidar();finalizarEditor(e,"piezas");});
    tareaForm.addEventListener("submit",e=>{e.preventDefault();if(editorIndice===null&&tareas.length>=100)return;if(!tareaForm.reportValidity())return;const segundos=numero(tareaForm.elements.tiempo.value)*(tareaForm.elements.unidad.value==="minutos"?60:1);if(!Number.isFinite(segundos)||segundos<=0)return;
      const t={nombre:tareaForm.elements.nombre.value,segundos:String(Number(segundos.toFixed(6)))};if(editorIndice===null)tareas.push(t);else tareas[editorIndice]=t;renderListas();invalidar();finalizarEditor(e,"tareas");});
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
        const inicial=d||recetas.find(r=>!r.unidad_id)||recetas[0]||{unidad_id:form.elements.unidad_produccion_ui.dataset.unidadInicial||""};unidad=String(inicial.unidad_id||"");form.elements.unidad_produccion_ui.value=unidad;cargar(inicial);
        form.elements.produccion_huella.value="";
        document.getElementById("producto-fabricacion-calcular").textContent="Calcular costo unitario";
      }estado();
    },
    mostrarError(c){const g=c.closest("[data-fabricacion-grupo]");if(g)tab(g.dataset.fabricacionGrupo);},
    validar() {
      if(form.elements.tipo.value!=="produccion")return true;
      if(!habilitado)return false;
      document.getElementById("producto-fabricacion-error").hidden=true;
      const d=actual();if(!piezas.length&&!tareas.length)return error("Agregá los componentes o las tareas del producto.");
      if(tareas.length&&(!d.tarifa_id||(form.elements.tarifa_produccion_ui.selectedOptions[0]&&form.elements.tarifa_produccion_ui.selectedOptions[0].disabled))){tab("tareas");return error("Seleccioná la tarifa de mano de obra del taller.",form.elements.tarifa_produccion_ui);}
      for(const c of panel.querySelectorAll("input[data-campo],select[data-campo]")) {
        if(!c.validity.valid || (c.tagName==="SELECT" && c.selectedOptions[0]&&c.selectedOptions[0].disabled))return error("Revisá los recursos, cantidades y tiempos de fabricación.",c);
      }
      form.elements.produccion_json.value=JSON.stringify(d);return true;
    },
    resumen(){return piezas.length+" componentes · "+tareas.length+" tareas · "+formato(tareas.reduce((s,t)=>s+numero(t.segundos),0))+" segundos por unidad. "+resultado;}
  };
})();
