(() => {
  const dialogo=document.getElementById('area-dialogo'),form=document.getElementById('area-form'),confirmar=document.getElementById('area-confirmar');
  if(!dialogo)return;let enviando=false;
  document.getElementById('area-abrir')?.addEventListener('click',()=>dialogo.showModal());
  document.querySelectorAll('[data-area-cerrar]').forEach(b=>b.addEventListener('click',()=>dialogo.close()));
  form.addEventListener('submit',e=>{e.preventDefault();if(!enviando&&form.reportValidity()){confirmar.showModal();document.getElementById('area-no').focus();}});
  document.getElementById('area-no').addEventListener('click',()=>confirmar.close());
  document.getElementById('area-si').addEventListener('click',()=>{if(enviando||!confirmar.open)return;enviando=true;document.getElementById('area-si').disabled=true;HTMLFormElement.prototype.submit.call(form);});
  if(document.getElementById('area-reabrir'))dialogo.showModal();
})();
