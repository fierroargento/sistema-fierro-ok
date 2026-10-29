(() => {
 'use strict';let pendiente=null,enviando=false,origen=null;
 const confirmar=document.getElementById('material-confirmar');if(!confirmar)return;
 const scrollKey='compras-materiales-scroll';
 document.querySelectorAll('[data-material-abrir]').forEach(b=>b.addEventListener('click',()=>{origen=b;document.getElementById(b.dataset.materialAbrir).showModal();}));
 document.querySelectorAll('[data-material-cerrar]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
 document.querySelectorAll('dialog').forEach(d=>d.addEventListener('close',()=>{d.querySelector('form')?.reset();origen?.focus({preventScroll:true});}));
 document.querySelector('[data-material-auto]')?.showModal();
 const fallo=document.getElementById('material-error');
 if(fallo){const datos=JSON.parse(fallo.textContent),v=datos.formulario;
   const f=Array.from(document.querySelectorAll('[data-material-confirm]')).find(f=>f.elements.accion.value===v.accion&&(v.accion==='crear'||f.elements.insumo_id.value===v.insumo_id&&f.elements.moneda.value===v.moneda));
   if(f){for(const [k,valor] of Object.entries(v)){if(f.elements[k]&&k!=='accion')f.elements[k].value=valor;}const p=document.createElement('p');p.className='personal-error';p.setAttribute('role','alert');p.textContent=datos.mensaje;f.querySelector('.personal-dialog-body').prepend(p);f.closest('dialog').showModal();}
 }
 document.querySelectorAll('[data-material-confirm]').forEach(f=>f.addEventListener('submit',e=>{e.preventDefault();if(enviando||!f.reportValidity())return;pendiente=f;confirmar.showModal();document.getElementById('material-no').focus();}));
 confirmar.addEventListener('cancel',()=>{pendiente=null;});
 document.getElementById('material-no').addEventListener('click',()=>{pendiente=null;confirmar.close();});
 document.getElementById('material-si').addEventListener('click',()=>{if(!pendiente||enviando)return;enviando=true;try{sessionStorage.setItem(scrollKey,String(window.scrollY));}catch(_){}HTMLFormElement.prototype.submit.call(pendiente);});
 try{const y=sessionStorage.getItem(scrollKey);if(y!==null){sessionStorage.removeItem(scrollKey);requestAnimationFrame(()=>window.scrollTo(0,Number(y)));}}catch(_){}
})();
