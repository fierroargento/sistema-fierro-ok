"""Items, evidencias y control final de postventa sin efectos operativos."""
import hashlib,io,json
from services.fechas import ahora_utc_naive
from decimal import Decimal,InvalidOperation
def agregar_item(datos,*,caso,producto,organizacion_id,unidad_negocio_id,Item,db_session):
 if caso is None or producto is None or int(caso.organizacion_id)!=int(organizacion_id) or int(caso.unidad_negocio_id)!=int(unidad_negocio_id) or int(producto.organizacion_id)!=int(organizacion_id):raise ValueError("Caso o producto fuera del contexto activo.")
 try:cantidad=Decimal(str(datos.get("cantidad") or "0").replace(",","."))
 except InvalidOperation:raise ValueError("Cantidad invalida.")
 condicion=str(datos.get("condicion") or "sin_recibir")
 if cantidad<=0 or condicion not in {"sin_recibir","nuevo","usado","danado","incompleto"}:raise ValueError("Cantidad o condicion invalida.")
 item=Item(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,caso_id=caso.id,producto_id=producto.id,cantidad=cantidad,condicion=condicion,detalle=str(datos.get("detalle_item") or "").strip() or None,recibido=False,afecta_stock=False);db_session.add(item);db_session.commit();return item
def agregar_evidencia(datos,*,caso,organizacion_id,unidad_negocio_id,Evidencia,db_session):
 if caso is None or int(caso.organizacion_id)!=int(organizacion_id) or int(caso.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("El caso no pertenece al contexto activo.")
 tipo=str(datos.get("tipo_evidencia") or "").strip();referencia=str(datos.get("referencia") or "").strip()
 if tipo not in {"foto","video","documento","nota_interna"} or len(referencia)<5:raise ValueError("Tipo y referencia de evidencia son obligatorios.")
 huella=hashlib.sha256(f"{caso.id}|{tipo}|{referencia}".encode()).hexdigest();e=Evidencia(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,caso_id=caso.id,tipo=tipo,referencia=referencia,huella=huella,verificada=False,enviada=False);db_session.add(e);db_session.commit();return e
def control_final(*,organizacion_id,unidad_negocio_id,casos,propuestas,items,evidencias,ahora=None):
 ahora=ahora or ahora_utc_naive();casos=[x for x in casos if int(x.organizacion_id)==int(organizacion_id) and int(x.unidad_negocio_id)==int(unidad_negocio_id)];ids={x.id for x in casos};propuestas=[x for x in propuestas if x.caso_id in ids];items=[x for x in items if x.caso_id in ids];evidencias=[x for x in evidencias if x.caso_id in ids];hallazgos=[]
 for c in casos:
  if c.estado not in {"cancelado","cerrado_sin_efecto"} and not any(x.caso_id==c.id for x in items):hallazgos.append({"codigo":"caso_sin_items","caso_id":c.id})
  if c.estado in {"diagnostico","propuesta"} and not any(x.caso_id==c.id for x in evidencias):hallazgos.append({"codigo":"caso_sin_evidencia","caso_id":c.id})
  if c.estado=="propuesta" and not any(x.caso_id==c.id for x in propuestas):hallazgos.append({"codigo":"caso_sin_resolucion","caso_id":c.id})
  if c.estado not in {"cancelado","cerrado_sin_efecto"} and (ahora-c.fecha_creacion).days>15:hallazgos.append({"codigo":"caso_vencido","caso_id":c.id})
 for x in items:
  if x.recibido or x.afecta_stock:hallazgos.append({"codigo":"item_con_stock","item_id":x.id})
 for x in evidencias:
  if x.verificada or x.enviada:hallazgos.append({"codigo":"evidencia_externa","evidencia_id":x.id})
 r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"cierre_postventa_no_ejecutable","aprobado":not hallazgos,"resumen":{"casos":len(casos),"items":len(items),"evidencias":len(evidencias),"propuestas":len(propuestas),"exposicion_centavos":sum(int(x.importe_centavos) for x in propuestas),"hallazgos":len(hallazgos)},"hallazgos":hallazgos,"controles":{"recepciones":0,"stock_movido":0,"reintegros":0,"creditos":0,"mensajes":0,"acciones_canal":0,"conexiones_externas":0}}
 r["huella_control"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest();return r
def exportar(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2,default=str).encode())
