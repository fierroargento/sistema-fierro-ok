(() => {
 'use strict';
 const confirmar=document.getElementById('cotizacion-confirmar');if(!confirmar)return;
 let pendiente=null,enviando=false,origen=null;
 document.querySelectorAll('[data-cotizacion-abrir]').forEach(b=>b.addEventListener('click',()=>{origen=b;document.getElementById(b.dataset.cotizacionAbrir).showModal();}));
 document.querySelectorAll('[data-cotizacion-cerrar]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
 document.querySelectorAll('dialog').forEach(d=>d.addEventListener('close',()=>{if(d!==confirmar)d.querySelectorAll('form').forEach(f=>f.reset());origen?.focus({preventScroll:true});}));
 document.querySelectorAll('[data-cotizacion-confirm]').forEach(f=>f.addEventListener('submit',e=>{e.preventDefault();if(enviando||!f.reportValidity())return;pendiente=f;document.getElementById('cotizacion-pregunta').textContent=f.dataset.cotizacionConfirm;confirmar.showModal();document.getElementById('cotizacion-cancelar').focus();}));
 document.getElementById('cotizacion-cancelar').addEventListener('click',()=>{pendiente=null;confirmar.close();});
 confirmar.addEventListener('cancel',()=>{pendiente=null;});
 document.getElementById('cotizacion-aceptar').addEventListener('click',()=>{if(!pendiente||enviando)return;enviando=true;try{sessionStorage.setItem('cotizaciones-scroll',String(window.scrollY));}catch(_){}HTMLFormElement.prototype.submit.call(pendiente);});
 document.querySelector('[data-cotizacion-auto]')?.showModal();
 try{const y=sessionStorage.getItem('cotizaciones-scroll');if(y!==null){sessionStorage.removeItem('cotizaciones-scroll');requestAnimationFrame(()=>window.scrollTo(0,Number(y)));}}catch(_){}
})();
