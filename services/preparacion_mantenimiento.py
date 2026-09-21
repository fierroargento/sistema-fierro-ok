"""Checklists, repuestos propuestos y expediente final de mantenimiento."""
import hashlib,io,json
from collections import defaultdict
from decimal import Decimal,InvalidOperation

def agregar_tarea(datos,*,plan,organizacion_id,unidad_negocio_id,Tarea,db_session):
    if plan is None or int(plan.organizacion_id)!=int(organizacion_id) or int(plan.unidad_negocio_id)!=int(unidad_negocio_id):raise ValueError("El plan no pertenece al contexto activo.")
    descripcion=str(datos.get("descripcion") or "").strip()
    try:orden=int(datos.get("orden"))
    except (TypeError,ValueError):raise ValueError("El orden de tarea no es valido.")
    if not descripcion or orden<=0:raise ValueError("Descripcion y orden positivo son obligatorios.")
    tarea=Tarea(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,plan_id=plan.id,orden=orden,descripcion=descripcion,obligatoria=True,completada=False)
    db_session.add(tarea);db_session.commit();return tarea

def proponer_repuesto(datos,*,orden,organizacion_id,unidad_negocio_id,Propuesta,db_session):
    if orden is None or int(orden.organizacion_id)!=int(organizacion_id) or int(orden.unidad_negocio_id)!=int(unidad_negocio_id) or orden.estado!="planificada":raise ValueError("La orden no admite propuestas.")
    codigo=str(datos.get("codigo_repuesto") or "").strip();descripcion=str(datos.get("descripcion") or "").strip()
    try:cantidad=Decimal(str(datos.get("cantidad") or "0").replace(",","."));costo=int(Decimal(str(datos.get("costo_estimado") or "0").replace(".","").replace(",","."))*100)
    except InvalidOperation:raise ValueError("Cantidad o costo invalido.")
    if not codigo or not descripcion or cantidad<=0 or costo<0:raise ValueError("Los datos del repuesto no son validos.")
    p=Propuesta(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,orden_mantenimiento_id=orden.id,codigo_repuesto=codigo,descripcion=descripcion,cantidad=cantidad,costo_estimado_centavos=costo,aprobada=False,reservado=False,afecta_stock=False)
    db_session.add(p);db_session.commit();return p

def expediente_mantenimiento(*,organizacion_id,unidad_negocio_id,planes,ordenes,tareas,repuestos):
    hallazgos=[];carga=defaultdict(lambda:{"ordenes":0,"costo_estimado_centavos":0});planes_ids={int(x.id) for x in planes if int(x.organizacion_id)==int(organizacion_id) and int(x.unidad_negocio_id)==int(unidad_negocio_id)}
    ordenes_validas={int(x.id):x for x in ordenes if int(x.organizacion_id)==int(organizacion_id) and int(x.unidad_negocio_id)==int(unidad_negocio_id)}
    for o in ordenes_validas.values():
        if o.estado=="planificada":clave=f"{o.fecha_prevista.isocalendar().year}-S{o.fecha_prevista.isocalendar().week:02d}";carga[(int(o.maquina_id),clave)]["ordenes"]+=1;carga[(int(o.maquina_id),clave)]["costo_estimado_centavos"]+=int(o.costo_estimado_centavos)
        if o.ejecutada or o.afecta_stock:hallazgos.append({"codigo":"orden_con_impacto","orden_id":o.id})
    for t in tareas:
        if int(t.plan_id) not in planes_ids:continue
        if t.completada:hallazgos.append({"codigo":"tarea_completada_indebidamente","tarea_id":t.id})
    costo_repuestos=0
    for p in repuestos:
        if int(p.orden_mantenimiento_id) not in ordenes_validas:continue
        costo_repuestos+=int(p.costo_estimado_centavos)
        if p.aprobada or p.reservado or p.afecta_stock:hallazgos.append({"codigo":"repuesto_con_impacto","propuesta_id":p.id})
    filas=[{"maquina_id":k[0],"semana":k[1],**v} for k,v in sorted(carga.items(),key=lambda x:(x[0][1],x[0][0]))]
    r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"expediente_mantenimiento_no_ejecutable","carga_semanal":filas,"planes":len(planes_ids),"ordenes":len(ordenes_validas),"tareas":sum(int(t.plan_id) in planes_ids for t in tareas),"repuestos_propuestos":sum(int(p.orden_mantenimiento_id) in ordenes_validas for p in repuestos),"costo_repuestos_centavos":costo_repuestos,"hallazgos":hallazgos,"aprobado":not hallazgos,"controles":{"ejecuciones":0,"reservas_stock":0,"movimientos_stock":0,"compras":0,"conexiones_externas":0}}
    r["huella_expediente"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest();return r
def exportar_expediente(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode())
