/* Consulta del maestro. Solo GET interno; cerrar conserva la posición de la lista. */
(() => {
  'use strict';
  const dialogo=document.getElementById('producto-vista-dialog');
  if(!dialogo)return;
  const contenido=document.getElementById('producto-vista-contenido');
  let controller=null,secuencia=0,origen=null;
  function mensaje(texto,error=false){
    const header=document.createElement('header');header.className='pv-header';
    const titulo=document.createElement('h2');titulo.id='producto-vista-title';titulo.textContent=error?'No se pudo abrir la ficha':'Ver producto';
    const cerrar=document.createElement('button');cerrar.type='button';cerrar.className='producto-close';cerrar.setAttribute('data-vista-cerrar','');cerrar.setAttribute('aria-label','Cerrar ficha');cerrar.textContent='×';header.append(titulo,cerrar);
    const estado=document.createElement('p');estado.className=error?'pv-alert':'pv-empty';estado.setAttribute('role',error?'alert':'status');estado.textContent=texto;
    contenido.replaceChildren(header,estado);
  }
  async function abrir(boton){
    origen=boton;const intento=++secuencia;
    if(controller)controller.abort();controller=new AbortController();const peticion=controller;
    mensaje('Cargando los datos guardados del producto…');dialogo.setAttribute('aria-busy','true');
    if(!dialogo.open)dialogo.showModal();
    const timer=setTimeout(()=>peticion.abort(),15000);
    try{
      const respuesta=await fetch(boton.dataset.verProducto,{method:'GET',credentials:'same-origin',headers:{Accept:'text/html'},signal:peticion.signal});
      if(intento!==secuencia||!dialogo.open)return;
      if(!respuesta.ok||respuesta.redirected)throw new Error('No se pudo consultar el producto. Revisá tu sesión o recargá el listado.');
      const html=await respuesta.text();
      if(intento!==secuencia||!dialogo.open)return;
      // Contenido de una plantilla Jinja propia, con escape HTML y acceso tenant.
      const fragmento=document.createElement('template');fragmento.innerHTML=html;
      if(!fragmento.content.querySelector('#producto-vista-title')||!fragmento.content.querySelector('[data-vista-panel]'))throw new Error('La respuesta no corresponde a una ficha. Actualizá el listado e intentá nuevamente.');
      contenido.replaceChildren(fragmento.content);
      contenido.querySelector('[data-vista-cerrar]').focus({preventScroll:true});
    }catch(error){if(intento===secuencia&&dialogo.open)mensaje(error.name==='AbortError'?'La consulta demoró demasiado. Cerrá y volvé a intentarlo.':error.message,true);}
    finally{clearTimeout(timer);if(intento===secuencia)dialogo.removeAttribute('aria-busy');}
  }
  document.querySelectorAll('[data-ver-producto]').forEach(b=>b.addEventListener('click',()=>abrir(b)));
  dialogo.addEventListener('close',()=>{secuencia++;if(controller)controller.abort();dialogo.removeAttribute('aria-busy');contenido.replaceChildren();if(origen&&origen.isConnected)origen.focus({preventScroll:true});});
  dialogo.addEventListener('click',e=>{
    if(e.target.closest('[data-vista-cerrar]')){dialogo.close();return;}
    const tab=e.target.closest('[data-vista-tab]');if(tab)mostrar(tab);
  });
  function mostrar(tab){
    contenido.querySelectorAll('[data-vista-tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});
    contenido.querySelectorAll('[data-vista-panel]').forEach(p=>p.hidden=p.dataset.vistaPanel!==tab.dataset.vistaTab);
    const scroll=contenido.querySelector('.pv-scroll');if(scroll)scroll.scrollTop=0;
  }
  dialogo.addEventListener('keydown',e=>{
    const tab=e.target.closest('[data-vista-tab]');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
    e.preventDefault();const tabs=Array.from(contenido.querySelectorAll('[data-vista-tab]')),i=tabs.indexOf(tab);
    const indice=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length;
    mostrar(tabs[indice]);tabs[indice].focus({preventScroll:true});
  });
})();
