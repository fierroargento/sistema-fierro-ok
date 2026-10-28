(() => {
  'use strict';
  const workspace=document.getElementById('personal-gestion');
  if(workspace){
    workspace.showModal();
    workspace.querySelectorAll('[data-personal-gestion-cerrar]').forEach(b=>b.addEventListener('click',()=>workspace.close()));
    workspace.querySelectorAll('form[method="post"]').forEach(f=>{
      if(!f.elements.gestionar){const i=document.createElement('input');i.type='hidden';i.name='gestionar';i.value='1';f.append(i);}
    });
  }
  const dirty=new WeakSet();
  document.addEventListener('close',e=>{if(e.target.matches?.('.personal-dialog'))e.target.querySelectorAll('form').forEach(f=>dirty.delete(f));},true);
  const id=window.location.pathname.match(/personal\/(\d+)/)?.[1];
  const section=window.location.pathname.endsWith('/horarios')?'horarios':new URL(window.location.href).searchParams.get('seccion')||'datos';
  const scrollKey='personal-dialog-scroll-'+id+'-'+section;
  if(workspace){
    workspace.querySelectorAll('a[href]').forEach(a=>{
      const u=new URL(a.href,window.location.href);
      if(u.origin===window.location.origin&&u.pathname==='/admin/personal/'+id&&u.searchParams.has('seccion')){u.searchParams.set('gestionar','1');a.href=u.href;}
    });
    try{const y=sessionStorage.getItem(scrollKey);if(y!==null){sessionStorage.removeItem(scrollKey);requestAnimationFrame(()=>{workspace.scrollTop=Number(y);});}}catch(_){}
    document.addEventListener('click',e=>{if(e.target.closest('#personal-si,#semana-si'))try{sessionStorage.setItem(scrollKey,String(workspace.scrollTop));}catch(_){}},true);
  }
  document.addEventListener('input',e=>{if(e.target.form?.closest('.personal-dialog'))dirty.add(e.target.form);});
  document.addEventListener('change',e=>{if(e.target.form?.closest('.personal-dialog'))dirty.add(e.target.form);});
  document.addEventListener('click',e=>{
    const a=e.target.closest('a[href]');if(!a||!a.closest('.personal-dialog'))return;
    const dialog=a.closest('.personal-dialog');
    const forms=dialog.matches('form')?[dialog]:Array.from(dialog.querySelectorAll('form'));
    if(forms.some(f=>dirty.has(f))&&!window.confirm('Hay cambios sin guardar. ¿Descartarlos y continuar?'))e.preventDefault();
  });
})();
