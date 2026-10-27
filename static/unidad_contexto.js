"use strict";
(() => {
  const script=document.currentScript;
  const unidad=script?.dataset.unidad;
  if(!unidad)return;
  function preparar(raiz){
    const forms=raiz.matches?.('form')?[raiz]:Array.from(raiz.querySelectorAll?.('form')||[]);
    for(const form of forms){
      if((form.method||'get').toLowerCase()==='get')continue;
      const url=new URL(form.action||location.href,location.href);
      if(url.origin!==location.origin||form.querySelector('[name="unidad_contexto_id"]'))continue;
      const campo=document.createElement('input');campo.type='hidden';campo.name='unidad_contexto_id';campo.value=unidad;form.append(campo);
    }
  }
  document.addEventListener('click',event=>{
    const boton=event.target.closest('[data-unidad-cancelar]');
    if(!boton)return;
    const form=boton.closest('form'),editor=boton.closest('details');
    form?.reset();
    if(editor){editor.open=false;editor.querySelector('summary')?.focus({preventScroll:true});}
  });
  document.addEventListener('submit',event=>{
    const mensaje=event.target.dataset.unidadConfirmar;
    if(mensaje&&!event.defaultPrevented&&!window.confirm(mensaje))event.preventDefault();
  });
  preparar(document);
  new MutationObserver(cambios=>{for(const c of cambios)for(const n of c.addedNodes)if(n.nodeType===1)preparar(n);}).observe(document.body,{childList:true,subtree:true});
  const original=window.fetch;
  window.fetch=function(input,options){
    const url=new URL(input instanceof Request?input.url:input,location.href);
    const method=String(options?.method||(input instanceof Request?input.method:'GET')).toUpperCase();
    if(url.origin===location.origin&&!['GET','HEAD','OPTIONS'].includes(method)){
      const headers=new Headers(options?.headers||(input instanceof Request?input.headers:undefined));
      if(!headers.has('X-Fierro-Unidad'))headers.set('X-Fierro-Unidad',unidad);
      options={...options,headers};
    }
    return original.call(this,input,options);
  };
})();
