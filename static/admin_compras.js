"use strict";
document.addEventListener("DOMContentLoaded", function () {
  const antiguas={'#compras-ordenes':'ordenes','#compras-recepciones':'recepciones','#compras-facturas':'facturas','#compras-proveedores':'proveedores','#compras-mapeos':'mapeos','#compras-propuestas':'propuestas'};
  const url=new URL(window.location.href),vista=antiguas[url.hash];
  if(vista&&!url.searchParams.has('vista')){url.hash='';url.searchParams.set('vista',vista);window.location.replace(url.href);return;}

  const form=document.querySelector('[data-buscar-proveedor]');
  if(form){
    const campo=form.elements.identidad_proveedor,elegido=form.elements.proveedor_a_vincular;
    const resultados=form.querySelector('[data-proveedor-resultados]'),aviso=form.querySelector('[data-proveedor-aviso]');
    let timer=null,control=null,revision=0,nombre='';
    async function buscar(){
      const consulta=campo.value.trim(),actual=++revision;control?.abort();resultados.replaceChildren();
      if(consulta.length<2){aviso.textContent='Escribí al menos 2 caracteres para buscar.';return;}
      control=new AbortController();aviso.textContent='Buscando…';
      try{
        const u=new URL(form.dataset.buscarProveedor,window.location.href);u.searchParams.set('q',consulta);u.searchParams.set('unidad_contexto_id',form.elements.unidad_contexto_id.value);
        const r=await fetch(u,{credentials:'same-origin',cache:'no-store',signal:control.signal});
        if(r.redirected||!r.headers.get('content-type')?.includes('application/json'))throw Error('Revisá tu sesión antes de buscar.');
        const data=await r.json();if(!r.ok)throw Error(data.error||'No se pudo buscar.');if(actual!==revision)return;
        aviso.textContent=data.proveedores.length?'Elegí el proveedor correcto. Se muestran hasta 20 coincidencias.':'No hay coincidencias en la empresa.';
        data.proveedores.forEach(p=>{
          const b=document.createElement('button');b.type='button';b.className='compras-proveedor-opcion';
          const titulo=document.createElement('strong'),detalle=document.createElement('span');titulo.textContent=p.nombre;detalle.textContent=p.codigo+' · CUIT '+(p.cuit||'sin informar');b.append(titulo,detalle);
          b.addEventListener('click',()=>{revision++;clearTimeout(timer);control?.abort();elegido.value=String(p.id);campo.value=p.nombre;nombre=p.nombre;resultados.replaceChildren();aviso.textContent='Seleccionado: '+p.nombre+' · '+p.codigo;form.querySelector('[type=submit]').focus();});
          resultados.append(b);
        });
      }catch(e){if(e.name!=='AbortError'&&actual===revision)aviso.textContent=e.message;}
    }
    campo.addEventListener('input',()=>{elegido.value='';nombre='';revision++;control?.abort();clearTimeout(timer);timer=setTimeout(buscar,250);});
    form.querySelector('[data-proveedor-cancelar]').addEventListener('click',()=>{form.reset();form.closest('details').open=false;});
    form.addEventListener('reset',()=>{revision++;clearTimeout(timer);control?.abort();resultados.replaceChildren();aviso.textContent='';nombre='';});
    form.addEventListener('submit',e=>{if(!elegido.value){e.preventDefault();clearTimeout(timer);buscar();return;}if(!window.confirm('¿Vincular '+nombre+' a esta unidad, conservando una sola ficha?'))e.preventDefault();});
  }

  document.querySelectorAll('.compras-page a[href^="#orden-editor-"], .compras-page a[href^="#recepcion-editor-"]').forEach(function (enlace) {
    enlace.addEventListener("click", function () {
      const fila = document.getElementById(enlace.hash.slice(1));
      const editor = fila && fila.querySelector("details");
      if (editor) editor.open = true;
    });
  });
});
