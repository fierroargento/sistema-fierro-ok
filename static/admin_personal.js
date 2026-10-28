(() => {
  'use strict';
  const contenido = document.getElementById('personal-datos');
  if (!contenido) return;
  const datos = JSON.parse(contenido.textContent), form = document.getElementById('personal-form');
  const editor = document.getElementById('personal-editor'), confirm = document.getElementById('personal-confirm');
  const vista = document.getElementById('personal-vista'), error = document.getElementById('personal-form-error');
  const scrollKey = 'personal-scroll-' + document.querySelector('.personal-page').dataset.organizacion;
  let origen = null, pendiente = null, enviando = false;
  function tramosActuales() {
    return Array.from(form.querySelectorAll('.personal-tramo')).map(fila=>{
      const tramo={dia_semana:fila.closest('[data-personal-dia]').dataset.personalDia};
      fila.querySelectorAll('[data-tramo-campo]').forEach(c=>{tramo[c.dataset.tramoCampo]=c.value;});
      return tramo;
    });
  }
  function agregarTramo(dia, valores={}) {
    const seccion=form.querySelector('[data-personal-dia="'+dia+'"]');
    if(!seccion||form.querySelectorAll('.personal-tramo').length>=42)return;
    const fila=document.getElementById('personal-tramo-template').content.firstElementChild.cloneNode(true);
    fila.querySelectorAll('[data-tramo-campo]').forEach(c=>{
      if(c.dataset.tramoCampo in valores)c.value=valores[c.dataset.tramoCampo];
      c.disabled=!form.elements.cargar_horario_inicial.checked;
    });
    seccion.querySelector('[data-personal-tramos]').append(fila);
    actualizarHoras();
    return fila;
  }
  form.addEventListener('click',e=>{
    const agregar=e.target.closest('[data-personal-agregar-tramo]');
    if(agregar){const fila=agregarTramo(agregar.dataset.personalAgregarTramo);fila?.querySelector('input').focus();}
    const quitar=e.target.closest('[data-personal-quitar-tramo]');
    if(quitar){const dia=quitar.closest('[data-personal-dia]');quitar.closest('.personal-tramo').remove();actualizarHoras();dia.querySelector('[data-personal-agregar-tramo]').focus({preventScroll:true});}
  });
  function restaurarTramos(valores) {
    form.querySelectorAll('[data-personal-tramos]').forEach(n=>n.replaceChildren());
    let tramos=[];
    try{tramos=JSON.parse(valores.inicial_tramos||'[]');}catch(_){}
    if(Array.isArray(tramos))tramos.slice(0,42).forEach(t=>{if(t&&typeof t==='object'&&/^[0-6]$/.test(String(t.dia_semana)))agregarTramo(t.dia_semana,t);});
    actualizarHoras();
  }
  function actualizarHoras() {
    const auto=form.elements.cargar_horario_inicial.checked;
    const mensual=form.elements.inicial_horas_mensuales;
    mensual.closest('label').hidden=auto;
    mensual.disabled=auto||!form.elements.cargar_sueldo_inicial.checked||form.elements.accion.value==='editar';
    mensual.required=!mensual.disabled;
    const resumen=form.querySelector('[data-personal-horas-calculo]');
    resumen.hidden=!auto;
    const minutos=v=>{const p=v.split(':').map(Number);return p.length===2?p[0]*60+p[1]:NaN;};
    const tramos=tramosActuales();
    form.elements.inicial_tramos.value=JSON.stringify(tramos);
    let total=0,valido=tramos.length>0;
    for(const t of tramos){
      const duracion=minutos(t.salida)-minutos(t.entrada)+(t.nocturno==='1'?1440:0);
      const pausa=Number(t.pausa_minutos),neto=duracion-pausa;
      if(!Number.isFinite(neto)||duracion<=0||duracion>960||pausa<0||neto<=0)valido=false;
      else total+=neto;
    }
    form.querySelectorAll('[data-personal-dia]').forEach(dia=>{
      dia.querySelector('[data-personal-dia-libre]').hidden=!!dia.querySelector('.personal-tramo');
      dia.querySelector('[data-personal-agregar-tramo]').disabled=tramos.length>=42;
    });
    resumen.textContent=valido?'Horas mensuales automáticas: '+(total/60*52/12).toFixed(2)+' h. Suma de tramos semanales netos de descansos × 52 ÷ 12 (promedio para costos).':'Agregá y completá los tramos de cada día para calcular las horas mensuales automáticamente.';
  }
  form.addEventListener('input',actualizarHoras);
  form.addEventListener('change',actualizarHoras);
  function actualizarOpcionales() {
    const edicion=form.elements.accion.value==='editar';
    form.querySelectorAll('[data-personal-opcional]').forEach(check=>{
      const panel=document.getElementById(check.dataset.personalOpcional);
      const habilitado=!edicion&&check.checked;
      panel.hidden=!habilitado;
      panel.querySelectorAll('input,select,textarea').forEach(c=>{c.disabled=!habilitado;});
    });
    actualizarHoras();
  }
  function actualizarCuenta() {
    const accion=form.elements.acceso_accion.value;
    form.querySelectorAll('[data-personal-cuenta]').forEach(label=>{
      const habilitado=label.dataset.personalCuenta===accion;
      label.hidden=!habilitado;label.querySelectorAll('input,select').forEach(c=>{c.disabled=!habilitado;c.required=habilitado;});
    });
    form.elements.password.required=accion==='crear';form.elements.password_confirm.required=accion==='crear';
  }
  form.querySelectorAll('[data-personal-opcional]').forEach(c=>c.addEventListener('change',actualizarOpcionales));
  form.elements.acceso_accion.addEventListener('change',actualizarCuenta);

  function abrir(fila, fallido) {
    form.reset();enviando = false;pendiente = null;
    const valores = fallido || fila || {activo:'1', unidad_negocio_id:datos.unidad_inicial};
    const editar = fallido ? fallido.accion === 'editar' : !!fila;
    // Las opciones bloqueadas por una edición anterior no se arrastran al alta.
    Array.from(form.elements.unidad_negocio_id.options).forEach(o => {o.disabled = false;});
    for (const campo of ['codigo','nombre','sector','puesto','observacion','unidad_negocio_id','huella','dni','cuil','fecha_nacimiento','fecha_ingreso','fecha_egreso','telefono','email','domicilio','localidad','provincia','contacto_emergencia','categoria','convenio','modalidad']) form.elements[campo].value = valores[campo] ?? '';
    form.elements.activo.value = valores.activo === true || valores.activo === '1' ? '1' : '0';
    form.elements.accion.value = editar ? 'editar' : 'crear';
    form.elements.empleado_id.value = valores.empleado_id || valores.id || '';
    form.elements.codigo.readOnly = editar;
    form.elements.sector.readOnly=editar&&!!valores.sector_estructurado;
    Array.from(form.elements.unidad_negocio_id.options).forEach(o => {
      o.disabled = o.value === '' && (editar ? !!valores.unidad_negocio_id : true);
    });
    document.getElementById('personal-identidad-aviso').hidden = !editar;
    form.querySelectorAll('[data-personal-solo-alta]').forEach(n=>{n.hidden=editar;});
    form.querySelectorAll('[data-personal-solo-edicion]').forEach(n=>{n.hidden=!editar;});
    for(const campo of ['cargar_sueldo_inicial','cargar_horario_inicial']) {
      form.elements[campo].checked=!editar&&valores[campo]==='1';form.elements[campo].disabled=editar;
    }
    for(const c of form.elements) {
      if(!c.name?.startsWith('inicial_')||!(c.name in valores))continue;
      if(c.type==='checkbox')c.checked=(Array.isArray(valores[c.name])?valores[c.name]:[valores[c.name]]).includes(c.value);
      else c.value=valores[c.name];
    }
    restaurarTramos(valores);
    actualizarOpcionales();
    document.getElementById('personal-sueldo-actual').textContent='Sueldo: '+(valores.sueldo_resumen||'Sin sueldo cargado');
    document.getElementById('personal-horario-actual').textContent='Horario laboral: '+(valores.horario_resumen||'Sin horario cargado');
    const base='/admin/personal/'+(valores.id||valores.empleado_id||'');
    document.getElementById('personal-ir-sueldo').href=base+'?seccion=sueldos';
    document.getElementById('personal-ir-horario').href=base+'?seccion=horarios';
    form.elements.revision_accesos.value=valores.revision_accesos||'0';
    form.elements.username.value=valores.username||'';
    form.elements.usuario_organizacion_id.value=valores.usuario_organizacion_id||'';
    form.elements.acceso_accion.value=valores.acceso_accion||'conservar';
    for(const o of form.elements.acceso_accion.options)o.disabled=!!valores.usuario_sistema&&o.value!=='conservar';
    form.elements.quitar_codigo_alarma.checked=valores.quitar_codigo_alarma==='1';
    document.getElementById('personal-acceso-estado').textContent=(valores.usuario_sistema?'Usuario: '+valores.usuario_sistema+' · '+(valores.usuario_habilitado?'Habilitado':'Sin acceso habilitado'):'Sin usuario vinculado')+' · '+(valores.tiene_codigo_alarma?'Código de alarma configurado':'Sin código de alarma');
    actualizarCuenta();

    document.getElementById('personal-titulo').textContent = editar ? 'Gestionar · ' + valores.codigo : 'Nuevo empleado';
    document.getElementById('personal-guardar').disabled = false;
    document.getElementById('personal-guardar').textContent = 'Guardar ficha';
    error.hidden = !fallido;error.textContent = fallido ? datos.error : '';
    editor.showModal();(editar ? form.elements.nombre : form.elements.codigo).focus();
  }
  document.querySelectorAll('[data-personal-nuevo]').forEach(b => b.addEventListener('click', () => {origen=b;abrir(null,null);}));
  document.querySelectorAll('[data-personal-editar]').forEach(b => b.addEventListener('click', () => {
    origen=b;const fila=datos.filas.find(f=>String(f.id)===b.dataset.personalEditar);if(fila)abrir(fila,null);
  }));
  document.querySelectorAll('[data-personal-ver]').forEach(b => b.addEventListener('click', () => {
    origen=b;const fila=datos.filas.find(f=>String(f.id)===b.dataset.personalVer);if(!fila)return;
    const detalle=document.getElementById('personal-detalle');detalle.replaceChildren();
    for (const [titulo,valor] of [['Legajo',fila.codigo],['Nombre y apellido',fila.nombre],['Sector',fila.sector],['Puesto',fila.puesto],['Unidad',Array.from(form.elements.unidad_negocio_id.options).find(o=>o.value===String(fila.unidad_negocio_id||''))?.textContent],['Estado',fila.activo?'Activo':'Inactivo'],['Observaciones',fila.observacion]]) {
      const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=titulo;dd.textContent=valor||'Sin definir';detalle.append(dt,dd);
    }
    vista.showModal();
  }));
  document.querySelectorAll('[data-personal-cerrar]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
  for (const dialogo of [editor,vista]) dialogo.addEventListener('close',()=>{dialogo.querySelectorAll('input[type=password]').forEach(c=>{c.value='';});pendiente=null;if(origen?.isConnected)origen.focus({preventScroll:true});});
  function pedirConfirmacion(f,mensaje) {
    if(enviando||!f.reportValidity())return;
    pendiente=f;document.getElementById('personal-confirm-mensaje').textContent=mensaje;
    confirm.showModal();document.getElementById('personal-no').focus();
  }
  form.addEventListener('submit',e=>{e.preventDefault();pedirConfirmacion(form,'¿Guardar los datos de este empleado?');});
  document.querySelectorAll('[data-personal-confirm]').forEach(f=>f.addEventListener('submit',e=>{
    e.preventDefault();pedirConfirmacion(f,f.dataset.personalConfirm);
  }));
  document.querySelectorAll('[data-personal-abrir]').forEach(b=>b.addEventListener('click',()=>{
    const dialogo=document.getElementById(b.dataset.personalAbrir);if(dialogo)dialogo.showModal();
  }));
  confirm.addEventListener('cancel',()=>{pendiente=null;});
  document.getElementById('personal-no').addEventListener('click',()=>{pendiente=null;confirm.close();});
  document.getElementById('personal-si').addEventListener('click',()=>{
    if(!pendiente||enviando)return;
    const destino=pendiente;pendiente=null;enviando=true;confirm.close();
    try{sessionStorage.setItem(scrollKey,String(window.scrollY));}catch(_){}
    destino.querySelectorAll('[type=submit]').forEach(b=>{b.disabled=true;b.textContent='Guardando…';});
    HTMLFormElement.prototype.submit.call(destino);
  });
  try{const y=sessionStorage.getItem(scrollKey);if(y!==null){sessionStorage.removeItem(scrollKey);requestAnimationFrame(()=>window.scrollTo(0,Number(y)));}}catch(_){}
  const mostrarAlarma=document.getElementById('personal-alarma-mostrar');
  if(mostrarAlarma){
    const valor=document.getElementById('personal-alarma-valor'),aviso=document.getElementById('personal-alarma-error');
    let visible=false,timer=null,version=0;
    function ocultar(){version++;visible=false;clearTimeout(timer);valor.textContent='••••••';mostrarAlarma.textContent='Mostrar código';mostrarAlarma.disabled=false;}
    mostrarAlarma.addEventListener('click',async()=>{
      if(visible){ocultar();return;}
      const intento=++version;mostrarAlarma.disabled=true;aviso.textContent='';
      try{
        const body=new URLSearchParams({_csrf_token:form.elements._csrf_token.value});
        const r=await fetch(mostrarAlarma.dataset.url,{method:'POST',credentials:'same-origin',cache:'no-store',body});
        if(r.redirected||!r.headers.get('content-type')?.includes('application/json'))throw Error('Revisá tu sesión antes de consultar el código.');
        const data=await r.json();if(!r.ok)throw Error(data.error||'No se pudo consultar el código.');
        if(intento!==version||document.hidden)return;
        valor.textContent=data.codigo||'No configurado';visible=true;mostrarAlarma.textContent='Ocultar código';timer=setTimeout(ocultar,30000);
      }catch(e){if(intento===version)aviso.textContent=e.message;}
      finally{if(intento===version)mostrarAlarma.disabled=false;}
    });
    document.addEventListener('visibilitychange',()=>{if(document.hidden)ocultar();});window.addEventListener('pagehide',ocultar);
  }
  if(datos.formulario_error)abrir(null,datos.formulario_error);
  const camposFallidos=document.getElementById('personal-accion-error');
  if(camposFallidos){
    const valores=JSON.parse(camposFallidos.textContent);
    for(const f of document.querySelectorAll('[data-personal-confirm]')){
      if(f.elements.accion?.value!==valores.accion)continue;
      if(valores.registro_id&&f.elements.registro_id?.value!==valores.registro_id)continue;
      for(const [nombre,valor] of Object.entries(valores)){
        const c=f.elements[nombre];if(c&&c.tagName&&!['_csrf_token'].includes(nombre))c.value=valor;
      }
    }
  }
  if(document.getElementById('personal-autoeditar'))document.querySelector('[data-personal-editar]')?.click();
  const reabrir=document.getElementById('personal-reabrir');
  if(reabrir){const dialogo=document.getElementById(reabrir.dataset.dialogo);if(dialogo)dialogo.showModal();}
})();
