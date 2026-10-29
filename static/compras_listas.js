(() => {
 'use strict';
 const raiz=document.querySelector('.compras-listas'),confirmar=document.getElementById('lista-confirmar');if(!raiz||!confirmar)return;
 let pendiente=null,origen=null,enviando=false;
 const key='compras-listas-scroll-'+raiz.dataset.unidad+'-'+raiz.dataset.proveedor;
 function recordar(){try{sessionStorage.setItem(key,String(window.scrollY));}catch(_){}}
 raiz.querySelectorAll('[data-lista-abrir]').forEach(b=>b.addEventListener('click',()=>{origen=b;document.getElementById(b.dataset.listaAbrir)?.showModal();}));
 raiz.querySelectorAll('[data-lista-cerrar]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
 raiz.querySelectorAll('dialog').forEach(d=>d.addEventListener('close',()=>{if(d!==confirmar)d.querySelectorAll('form').forEach(f=>f.reset());origen?.focus({preventScroll:true});}));
 raiz.querySelectorAll('[data-lista-confirm]').forEach(f=>f.addEventListener('submit',e=>{e.preventDefault();if(enviando||!f.reportValidity())return;pendiente=f;document.getElementById('lista-confirmar-mensaje').textContent=f.dataset.listaConfirm;confirmar.showModal();document.getElementById('lista-no').focus();}));
 document.getElementById('lista-no').addEventListener('click',()=>{pendiente=null;confirmar.close();});
 confirmar.addEventListener('cancel',()=>{pendiente=null;});
 document.getElementById('lista-si').addEventListener('click',()=>{if(!pendiente||enviando)return;enviando=true;recordar();HTMLFormElement.prototype.submit.call(pendiente);});
 raiz.querySelectorAll('form:not([data-lista-confirm])').forEach(f=>f.addEventListener('submit',()=>recordar()));
 raiz.querySelectorAll('a[href*="ver="]').forEach(a=>a.addEventListener('click',recordar));
 raiz.querySelector('[data-lista-auto]')?.showModal();
 const fallo=document.getElementById('lista-error');
 if(fallo){const datos=JSON.parse(fallo.textContent),v=datos.formulario;
   const f=Array.from(raiz.querySelectorAll('form')).find(f=>f.elements.accion?.value===v.accion&&(!v.vinculo_id||f.elements.vinculo_id?.value===v.vinculo_id)&&(!v.moneda_proveedor||f.elements.moneda_proveedor?.value===v.moneda_proveedor));
   if(f){for(const [k,valor] of Object.entries(v)){const c=f.elements[k];if(c?.tagName&&c.type!=='file'&&!['_csrf_token','unidad_contexto_id','proveedor_id'].includes(k))c.value=valor;}const p=document.createElement('p');p.className='personal-error';p.setAttribute('role','alert');p.textContent=datos.mensaje;const d=f.closest('dialog');if(d){d.querySelector('.personal-dialog-body')?.prepend(p);d.showModal();}}
 }
 try{const y=sessionStorage.getItem(key);if(y!==null){sessionStorage.removeItem(key);requestAnimationFrame(()=>window.scrollTo(0,Number(y)));}}catch(_){}
})();
