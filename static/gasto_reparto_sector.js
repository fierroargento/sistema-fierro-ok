(function(){
'use strict';
const scrollKey='reparto-scroll:'+location.pathname+location.search;
try{const y=sessionStorage.getItem(scrollKey);if(y!==null){sessionStorage.removeItem(scrollKey);requestAnimationFrame(()=>window.scrollTo(0,Number(y)));}}catch(e){}
document.querySelectorAll('[data-reparto-abrir]').forEach(b=>b.addEventListener('click',()=>{
 const d=document.getElementById(b.dataset.repartoAbrir),f=d.querySelector('form'),lista=f.querySelector('[data-reparto-filas]');
 const original=lista.innerHTML;f.reset();delete f.dataset.enviando;
 function filtrar(fila){const u=fila.querySelector('[name=sector_unidad]').value,s=fila.querySelector('[name=sector_area]');Array.from(s.options).forEach(o=>{o.disabled=!!o.dataset.unidad&&o.dataset.unidad!==u;o.hidden=o.disabled;});if(s.selectedOptions[0]?.disabled)s.value='';}
 function total(){const n=Array.from(lista.querySelectorAll('[name=sector_porcentaje]')).reduce((a,x)=>a+Number(x.value||0),0);f.querySelector('[data-reparto-total]').textContent='Total: '+n.toLocaleString('es-AR')+' % · requerido: 100 %';return n;}
 function conectar(fila){filtrar(fila);fila.querySelector('[name=sector_unidad]').addEventListener('change',()=>filtrar(fila));fila.querySelector('[data-reparto-quitar]').addEventListener('click',()=>{fila.remove();total();});fila.addEventListener('input',total);}
 function agregar(){if(lista.children.length>=50)return;const fila=f.querySelector('template').content.firstElementChild.cloneNode(true);lista.appendChild(fila);conectar(fila);total();}
 Array.from(lista.children).forEach(conectar);if(!lista.children.length)agregar();
 f.querySelector('[data-reparto-agregar]').onclick=agregar;total();
 f.querySelector('[data-reparto-cancelar]').onclick=()=>d.close();
 d.addEventListener('close',()=>{lista.innerHTML=original;f.reset();b.focus({preventScroll:true});},{once:true});
 f.onsubmit=e=>{if(Math.abs(total()-100)>0.000001){e.preventDefault();f.querySelector('[data-reparto-total]').textContent='El reparto debe sumar 100 %.';return;}if(f.dataset.enviando){e.preventDefault();return;}f.dataset.enviando='1';try{sessionStorage.setItem(scrollKey,String(window.scrollY));}catch(e){}};
 d.showModal();
}));
})();
