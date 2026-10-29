(() => {
 'use strict';
 const node=document.getElementById('datos-formulario-config');if(!node)return;
 const config=JSON.parse(node.textContent),mayusculas=new Set(config.mayusculas||[]),telefonos=new Set(config.telefonos||[]),fiscales=new Set(config.fiscales||[]);
 function telefono(valor){
   if(!valor.trim())return '';
   if(!/^[+0-9\s().-]+$/.test(valor))throw Error('Usá números y característica, sin letras ni internos.');
   let n=valor.replace(/\D/g,'');
   if(valor.trim().startsWith('+')&&!n.startsWith('54')){if(/^[1-9][0-9]{6,14}$/.test(n))return '+'+n;throw Error('Revisá el teléfono internacional.');}
   if(!(n.length===10&&!valor.trim().startsWith('+'))){
     if(n.startsWith('00'))n=n.slice(2);
     if(n.startsWith('549'))n=n.slice(3);else if(n.startsWith('54')){n=n.slice(2);if(n.startsWith('9'))n=n.slice(1);}
     n=n.replace(/^0+/,'');
     if(n.startsWith('15'))n=n.slice(2);else for(const area of [2,3,4])if(n.slice(area,area+2)==='15'&&n.length-2===10){n=n.slice(0,area)+n.slice(area+2);break;}
   }
   if(n.length!==10)throw Error('Completá característica y 10 dígitos nacionales. Ej.: +549 2920123456.');
   return '+549 '+n;
 }
 function tipo(c){if(!c.matches('input,textarea')||c.disabled||c.readOnly||['hidden','password','email','url','file','checkbox','radio'].includes(c.type))return '';if(c.dataset.formato==='conservar')return '';return mayusculas.has(c.name)?'mayusculas':telefonos.has(c.name)||c.type==='tel'?'telefono':fiscales.has(c.name)||c.name==='documento'&&c.value.replace(/\D/g,'').length===11?'fiscal':'';}
 function aplicar(c,enVivo=false,validar=true){
   const t=tipo(c);if(!t)return;
   const valor=c.value,pos=c.selectionStart,fin=c.selectionEnd;
   c.setCustomValidity('');
   if(t==='mayusculas'){
     c.value=valor.toUpperCase();
     if(document.activeElement===c&&pos!==null)c.setSelectionRange(valor.slice(0,pos).toUpperCase().length,valor.slice(0,fin).toUpperCase().length);
   }else if(t==='fiscal'){
     if(!/^[0-9\s.-]*$/.test(valor)){if(validar)c.setCustomValidity('CUIT/CUIL: usá sólo números, espacios o guiones.');return;}
     const n=valor.replace(/\D/g,'');
     if(n.length<=11){c.value=n.slice(0,2)+(n.length>2?'-'+n.slice(2,10):'')+(n.length>10?'-'+n.slice(10):'');
       if(document.activeElement===c&&pos!==null){const count=valor.slice(0,pos).replace(/\D/g,'').length;let p=0,k=0;while(p<c.value.length&&k<count){if(/\d/.test(c.value[p]))k++;p++;}c.setSelectionRange(p,p);}
     }
     if(validar&&!enVivo&&n.length!==0&&n.length!==11)c.setCustomValidity('CUIT/CUIL: completá los 11 dígitos.');
   }else if(!enVivo){try{c.value=telefono(valor);}catch(e){if(validar)c.setCustomValidity(e.message);}}
 }
 document.addEventListener('input',e=>aplicar(e.target,true));
 document.addEventListener('change',e=>aplicar(e.target));
 document.addEventListener('blur',e=>aplicar(e.target),true);
 document.addEventListener('focus',e=>aplicar(e.target,false,false),true);
 document.addEventListener('reset',e=>setTimeout(()=>iniciar(e.target),0));
 document.addEventListener('submit',e=>{
   if(!(e.target instanceof HTMLFormElement))return;
   e.target.querySelectorAll('input,textarea').forEach(c=>aplicar(c));
   if(!e.target.reportValidity()){e.preventDefault();e.stopImmediatePropagation();}
 },true);
 function iniciar(raiz){if(raiz.matches?.('input,textarea'))aplicar(raiz,false,false);raiz.querySelectorAll?.('input,textarea').forEach(c=>aplicar(c,false,false));}
 iniciar(document);
 new MutationObserver(registros=>{for(const r of registros)for(const n of r.addedNodes)if(n.nodeType===1)iniciar(n);}).observe(document.body,{childList:true,subtree:true});
 document.addEventListener('click',e=>{if(e.target.closest('[data-formato-volver]'))window.history.back();});
})();
