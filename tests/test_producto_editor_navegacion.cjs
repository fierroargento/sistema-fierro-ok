// Ejecutar con node --test tests/test_producto_editor_navegacion.cjs
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('static/admin_productos.js','utf8');
function entorno(editor){
 const botones=Array.from({length:8},()=>({parentElement:{},dataset:{},setAttribute(k,v){this[k]=v;},removeAttribute(k){delete this[k];}}));
 const pasos=['basicos','comercial','stock','costos','economia','imagenes','envios','resumen'].map(n=>({dataset:{paso:n,titulo:n},querySelector(){return {focus(){}}}}));
 const c={modoEditor:editor,pasoActual:0,maxVisitado:0,pasos,indicador:{querySelectorAll(){return botones;}},document:{getElementById(){return c.progreso;}},progreso:{},anterior:{},siguiente:{},guardar:{},dialogo:{querySelector(){return {scrollTop:10};}},armarResumen(){c.resumen=true;}};
 vm.createContext(c);vm.runInContext(source.slice(source.indexOf('  function mostrarPaso('),source.indexOf('  function irAPaso(')),c);
 return {...c,c,botones};
}
test('editor: secciones accesibles y guardar disponible sin recorrer pasos',()=>{
 const {c,botones}=entorno(true);c.mostrarPaso(0,false);
 assert.ok(botones.every(b=>!b.disabled));assert.ok(botones[7].parentElement.hidden);
 assert.ok(c.anterior.hidden&&c.siguiente.hidden);assert.equal(c.guardar.hidden,false);
 c.mostrarPaso(3,false);assert.equal(c.pasos[3].hidden,false);assert.equal(c.pasos[0].hidden,true);
 assert.equal(c.guardar.textContent,'Guardar cambios');
});
test('alta: conserva pasos progresivos y revisión antes de guardar',()=>{
 const {c,botones}=entorno(false);c.mostrarPaso(0,false);
 assert.equal(botones[1].disabled,true);assert.equal(c.guardar.hidden,true);
 assert.equal(c.siguiente.hidden,false);c.mostrarPaso(7,false);
 assert.equal(c.guardar.hidden,false);assert.equal(c.resumen,true);
});
