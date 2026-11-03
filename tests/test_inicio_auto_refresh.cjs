const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('static/inicio_auto_refresh.js','utf8');
function page(path='/'){
 const events={},winEvents={};let timer,reloads=0,cleared=0;
 const window={location:{pathname:path,search:'',href:'https://fierro.test'+path,origin:'https://fierro.test',reload(){reloads++;}},addEventListener(k,v){winEvents[k]=v;}};
 const document={currentScript:{dataset:{filtroStorageKey:'filtro'}},hidden:false,addEventListener(k,v){events[k]=v;}};
 vm.runInNewContext(source,{window,document,URL,Date,localStorage:{removeItem(){cleared++;}},setInterval(fn){timer=fn;}});
 return {events,winEvents,tick:()=>timer?.(),reloads:()=>reloads,cleared:()=>cleared,click(path,extra={}){winEvents.click({button:0,target:{closest:()=>({href:'https://fierro.test'+path,target:'',hasAttribute:()=>false})},...extra});}};
}
test('navegación lenta a Gastos y Pagos impide refrescos de Inicio',()=>{
 for(const target of ['/admin/gastos','/admin/comercial/cuentas-pagar']){
 const p=page();p.click(target);p.tick();p.winEvents.focus();p.events.visibilitychange();assert.equal(p.reloads(),0);
 }
});
test('Inicio sigue refrescando sin navegación y al regresar',()=>{const p=page();p.winEvents.focus();assert.equal(p.reloads(),1);p.click('/admin/gastos');p.winEvents.pageshow();p.winEvents.focus();assert.equal(p.reloads(),2);});
test('enlace cancelado o abierto en otra pestaña no desactiva Inicio',()=>{for(const extra of [{defaultPrevented:true},{ctrlKey:true},{metaKey:true}]){const p=page();p.click('/admin/gastos',extra);p.winEvents.focus();assert.equal(p.reloads(),1);}});
test('formulario que navega pausa; formulario cancelado conserva refresco',()=>{const p=page();p.winEvents.submit({target:{target:''}});p.winEvents.focus();assert.equal(p.reloads(),0);const q=page();q.winEvents.submit({defaultPrevented:true,target:{target:''}});q.winEvents.focus();assert.equal(q.reloads(),1);});
test('fuera de Inicio sólo limpia el filtro',()=>{const p=page('/admin/gastos');assert.equal(p.cleared(),1);p.tick();assert.equal(p.reloads(),0);});
