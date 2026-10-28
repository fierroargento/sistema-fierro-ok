(() => {
  'use strict';
  const resumen=document.querySelector('[data-dedicacion-resumen]');if(!resumen)return;
  const form=resumen.closest('form');
  const campos=Array.from(form.querySelectorAll('input[name^="area_porcentaje_"]'));
  const numero=v=>new Intl.NumberFormat('es-AR',{maximumFractionDigits:4}).format(v);
  function actualizar(){
    // Enteros de cuatro decimales: 33,3333 + 33,3333 + 33,3334 = 100 exacto.
    const validos=campos.every(c=>c.value.trim()!==''&&Number.isFinite(Number(c.value))&&Number(c.value)>=0&&Number(c.value)<=100&&c.validity.valid);
    const total=campos.reduce((s,c)=>s+Math.round(Number(c.value)*10000),0);
    const completa=validos&&total===1000000;
    resumen.classList.toggle('personal-dedicacion-completa',completa);
    resumen.classList.toggle('personal-dedicacion-pendiente',!completa);
    resumen.querySelector('[data-dedicacion-total]').textContent=validos?numero(total/10000)+'%':'—';
    resumen.querySelector('[data-dedicacion-estado]').textContent=!validos?'Revisá los porcentajes':completa?'Completa':total===0?'Sin asignación':total<1000000?'Falta '+numero((1000000-total)/10000)+'%':'Excede en '+numero((total-1000000)/10000)+'%';
  }
  form.addEventListener('input',actualizar);form.addEventListener('change',actualizar);actualizar();
})();
