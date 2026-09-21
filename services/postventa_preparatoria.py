"""Gestion tenant de postventa sin stock, dinero, mensajes o canales."""
import hashlib,io,json
def crear_caso(datos,*,pedido,organizacion_id,unidad_negocio_id,Caso,db_session,usuario_id=None):
 if pedido is None or int(pedido.organizacion_id)!=int(organizacion_id) or int(pedido.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("El pedido no pertenece al contexto activo.")
 tipo=str(datos.get("tipo") or "").strip();titulo=str(datos.get("titulo") or "").strip();descripcion=str(datos.get("descripcion") or "").strip()
 if tipo not in {"devolucion","garantia","reclamo","cambio"} or len(titulo)<3 or len(descripcion)<10:raise ValueError("Tipo, titulo y descripcion son obligatorios.")
 clave=hashlib.sha256(f"{organizacion_id}|{unidad_negocio_id}|{pedido.id}|{tipo}|{titulo.lower()}".encode()).hexdigest()
 caso=Caso(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,pedido_id=pedido.id,tipo=tipo,titulo=titulo,descripcion=descripcion,clave_idempotencia=clave,estado="abierto",contacto_externo=False,afecta_stock=False,afecta_saldo=False,creado_por_usuario_id=usuario_id);db_session.add(caso);db_session.commit();return caso
def proponer_resolucion(datos,*,caso,organizacion_id,unidad_negocio_id,Propuesta,db_session):
 if caso is None or int(caso.organizacion_id)!=int(organizacion_id) or int(caso.unidad_negocio_id)!=int(unidad_negocio_id) or caso.estado in {"cancelado","cerrado_sin_efecto"}:raise ValueError("El caso no admite propuestas en el contexto activo.")
 tipo=str(datos.get("tipo_resolucion") or "").strip();detalle=str(datos.get("detalle") or "").strip()
 try:importe=int(datos.get("importe_centavos") or 0)
 except ValueError:raise ValueError("El importe debe expresarse en centavos.")
 if tipo not in {"reposicion","reintegro","reparacion","cambio","rechazo"} or len(detalle)<5 or importe<0:raise ValueError("La propuesta es invalida.")
 p=Propuesta(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,caso_id=caso.id,tipo=tipo,detalle=detalle,importe_centavos=importe,aprobada=False,ejecutada=False,afecta_stock=False,emite_credito=False);caso.estado="propuesta";db_session.add(p);db_session.commit();return p
def cambiar_estado(caso,*,organizacion_id,unidad_negocio_id,estado,db_session):
 if caso is None or int(caso.organizacion_id)!=int(organizacion_id) or int(caso.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("El caso no pertenece al contexto activo.")
 permitidos={"abierto":{"diagnostico","cancelado"},"diagnostico":{"cancelado"},"propuesta":{"cerrado_sin_efecto","cancelado"}}
 if estado not in permitidos.get(caso.estado,set()):raise ValueError("La transicion no es valida o implicaria ejecucion.")
 caso.estado=estado;db_session.commit();return caso
def expediente_postventa(*,organizacion_id,unidad_negocio_id,casos,propuestas):
 casos=[x for x in casos if int(x.organizacion_id)==int(organizacion_id) and int(x.unidad_negocio_id)==int(unidad_negocio_id)];ids={x.id for x in casos};propuestas=[x for x in propuestas if int(x.organizacion_id)==int(organizacion_id) and int(x.unidad_negocio_id)==int(unidad_negocio_id)];hallazgos=[]
 for c in casos:
  if c.contacto_externo or c.afecta_stock or c.afecta_saldo:hallazgos.append({"codigo":"caso_con_impacto","caso_id":c.id})
 for p in propuestas:
  if p.caso_id not in ids:hallazgos.append({"codigo":"propuesta_huerfana","propuesta_id":p.id})
  if p.aprobada or p.ejecutada or p.afecta_stock or p.emite_credito:hallazgos.append({"codigo":"propuesta_ejecutable","propuesta_id":p.id})
 r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"postventa_preparatoria_no_ejecutable","aprobado":not hallazgos,"resumen":{"casos":len(casos),"abiertos":sum(x.estado not in {"cancelado","cerrado_sin_efecto"} for x in casos),"propuestas":len(propuestas),"importe_propuesto_centavos":sum(int(x.importe_centavos) for x in propuestas),"hallazgos":len(hallazgos)},"hallazgos":hallazgos,"controles":{"stock_movido":0,"reintegros":0,"notas_credito":0,"mensajes_enviados":0,"reclamos_canal":0,"conexiones_externas":0}}
 r["huella_expediente"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest();return r
def exportar(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode())
