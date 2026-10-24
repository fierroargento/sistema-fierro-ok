(() => {
  'use strict';
  const form=document.getElementById('semana-form');if(!form)return;
  const editar=form.dataset.editar==='1',dialogo=document.getElementById('semana-confirmar');
  let enviando=false;
  function agregar(dia,valores={}){
    if(!/^[0-6]$/.test(String(dia))||form.querySelectorAll('.personal-tramo').length>=42)return;
    const fila=document.getElementById('semana-fila').content.firstElementChild.cloneNode(true);
    fila.dataset.id=valores.id||'';fila.dataset.observacion=valores.observacion_horario||'';
    fila.querySelectorAll('[data-campo]').forEach(c=>{c.value=valores[c.dataset.campo]??(c.dataset.campo==='desde'?form.dataset.hoy:c.value);c.disabled=!editar;});
    form.querySelector('[data-dia="'+dia+'"] [data-filas]').append(fila);
    return fila;
  }
  function valores(){return Array.from(form.querySelectorAll('.personal-tramo')).map(fila=>{
    const f={id:fila.dataset.id,dia_semana:fila.closest('[data-dia]').dataset.dia,observacion_horario:fila.dataset.observacion};
    fila.querySelectorAll('[data-campo]').forEach(c=>{f[c.dataset.campo]=c.value;});return f;
  }).filter(f=>f.entrada||f.salida);}
  function resumen(){
    const filas=valores();document.getElementById('semana-valores').value=JSON.stringify(filas);
    const min=v=>{const t=v.split(':').map(Number);return t.length===2?t[0]*60+t[1]:NaN;};
    const total=filas.reduce((sum,f)=>sum+min(f.salida)-min(f.entrada)+(f.nocturno==='1'?1440:0)-Number(f.pausa_minutos||0),0);
    document.getElementById('semana-resumen').textContent=Number.isFinite(total)&&total>0?'Semana cargada: '+(total/60).toFixed(2)+' h netas. El costo utiliza las franjas vigentes hoy, sin contar los cortes entre entradas y salidas.':'Dejá sin entrada y salida los días libres.';
  }
  const iniciales=JSON.parse(document.getElementById('semana-datos').textContent);
  iniciales.forEach(f=>agregar(f.dia_semana,f));
  for(let dia=0;dia<7;dia++)if(!form.querySelector('[data-dia="'+dia+'"] .personal-tramo')){
    if(editar)agregar(dia);else{const p=document.createElement('p');p.textContent='Día libre';form.querySelector('[data-dia="'+dia+'"] [data-filas]').append(p);}
  }
  form.addEventListener('input',resumen);form.addEventListener('change',resumen);
  form.addEventListener('click',e=>{
    const boton=e.target.closest('[data-agregar]');if(boton)agregar(boton.dataset.agregar)?.querySelector('input').focus();
    const quitar=e.target.closest('[data-quitar]');if(quitar){const dia=quitar.closest('[data-dia]');quitar.closest('.personal-tramo').remove();dia.querySelector('[data-agregar]').focus({preventScroll:true});}
    resumen();
  });
  form.addEventListener('submit',e=>{
    e.preventDefault();if(!editar||enviando)return;
    const error=document.getElementById('semana-error');error.hidden=true;
    if(valores().some(f=>!f.entrada||!f.salida||!f.desde)) {error.textContent='Completá entrada, salida y vigencia de cada franja, o dejá el día libre.';error.hidden=false;return;}
    if(!form.reportValidity())return;
    resumen();dialogo.showModal();document.getElementById('semana-no').focus();
  });
  document.getElementById('semana-no').addEventListener('click',()=>dialogo.close());
  document.getElementById('semana-si').addEventListener('click',()=>{
    if(enviando||!editar||!dialogo.open)return;enviando=true;
    document.getElementById('semana-si').disabled=true;
    HTMLFormElement.prototype.submit.call(form);
  });
  resumen();
})();
