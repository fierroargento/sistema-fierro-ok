"""Planificacion integral de mantenimiento sin ejecucion real."""
import hashlib,io,json
from datetime import date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP

def _fecha(v):
    try:return date.fromisoformat(str(v or ""))
    except ValueError:raise ValueError("La fecha no es valida.")
def _centavos(v):
    try:n=Decimal(str(v or 0).replace(".","").replace(",","."))
    except InvalidOperation:raise ValueError("El costo estimado no es valido.")
    if n<0:raise ValueError("El costo estimado no puede ser negativo.")
    return int((n*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
def _validar_maquina(m,org,unidad):
    if m is None or int(m.organizacion_id)!=int(org) or int(m.unidad_negocio_id)!=int(unidad):raise ValueError("La maquina no pertenece al contexto activo.")

def crear_plan(datos,*,maquina,organizacion_id,unidad_negocio_id,Plan,db_session,usuario_id=None):
    _validar_maquina(maquina,organizacion_id,unidad_negocio_id);codigo=str(datos.get("codigo") or "").strip();nombre=str(datos.get("nombre") or "").strip()
    if not codigo or not nombre:raise ValueError("Codigo y nombre son obligatorios.")
    try:frecuencia=int(datos.get("frecuencia_dias"))
    except (TypeError,ValueError):raise ValueError("La frecuencia no es valida.")
    if frecuencia<=0:raise ValueError("La frecuencia debe ser positiva.")
    p=Plan(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,maquina_id=maquina.id,codigo=codigo,nombre=nombre,frecuencia_dias=frecuencia,
        proxima_fecha=_fecha(datos.get("proxima_fecha")),instrucciones=str(datos.get("instrucciones") or "").strip() or None,activo=False,ejecucion_habilitada=False,creado_por_usuario_id=usuario_id)
    db_session.add(p);db_session.commit();return p

def crear_orden(datos,*,maquina,plan,organizacion_id,unidad_negocio_id,Orden,db_session,usuario_id=None):
    _validar_maquina(maquina,organizacion_id,unidad_negocio_id)
    if plan is not None and (int(plan.organizacion_id)!=int(organizacion_id) or int(plan.unidad_negocio_id)!=int(unidad_negocio_id) or int(plan.maquina_id)!=int(maquina.id)):raise ValueError("El plan no corresponde a la maquina activa.")
    tipo=str(datos.get("tipo") or "").strip();descripcion=str(datos.get("descripcion") or "").strip();fecha=_fecha(datos.get("fecha_prevista"))
    if tipo not in {"preventivo","correctivo","inspeccion"}:raise ValueError("Tipo de mantenimiento invalido.")
    if not descripcion:raise ValueError("La descripcion es obligatoria.")
    costo=_centavos(datos.get("costo_estimado"));base=f"{organizacion_id}:{unidad_negocio_id}:{maquina.id}:{getattr(plan,'id',0)}:{tipo}:{fecha}:{descripcion}:{costo}"
    o=Orden(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,maquina_id=maquina.id,plan_id=getattr(plan,"id",None),tipo=tipo,fecha_prevista=fecha,
        descripcion=descripcion,costo_estimado_centavos=costo,clave_idempotencia=hashlib.sha256(base.encode()).hexdigest(),estado="planificada",ejecutada=False,afecta_stock=False,creado_por_usuario_id=usuario_id)
    db_session.add(o);db_session.commit();return o

def cancelar_orden(orden,*,organizacion_id,unidad_negocio_id,motivo,db_session):
    if int(orden.organizacion_id)!=int(organizacion_id) or int(orden.unidad_negocio_id)!=int(unidad_negocio_id) or orden.estado!="planificada" or orden.ejecutada or orden.afecta_stock:raise ValueError("La orden no puede cancelarse.")
    motivo=str(motivo or "").strip()
    if len(motivo)<5:raise ValueError("El motivo debe tener al menos cinco caracteres.")
    orden.estado="cancelada";orden.observacion=f"CANCELADA: {motivo}";db_session.commit();return orden

def controlar_mantenimiento(*,organizacion_id,unidad_negocio_id,planes,ordenes,hoy=None):
    hoy=hoy or date.today();hallazgos=[];agenda=[]
    validos={int(p.id):p for p in planes if int(p.organizacion_id)==int(organizacion_id) and int(p.unidad_negocio_id)==int(unidad_negocio_id)}
    for p in validos.values():
        dias=(p.proxima_fecha-hoy).days;agenda.append({"plan_id":p.id,"maquina_id":p.maquina_id,"proxima_fecha":p.proxima_fecha.isoformat(),"dias_restantes":dias,"estado":"vencido" if dias<0 else ("proximo" if dias<=15 else "programado")})
        if p.activo or p.ejecucion_habilitada:hallazgos.append({"codigo":"plan_indebidamente_habilitado","plan_id":p.id})
    costo=sum(int(o.costo_estimado_centavos) for o in ordenes if int(o.organizacion_id)==int(organizacion_id) and int(o.unidad_negocio_id)==int(unidad_negocio_id) and o.estado=="planificada")
    for o in ordenes:
        if int(o.organizacion_id)==int(organizacion_id) and int(o.unidad_negocio_id)==int(unidad_negocio_id) and (o.ejecutada or o.afecta_stock):hallazgos.append({"codigo":"orden_con_impacto","orden_id":o.id})
    r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"mantenimiento_preparatorio_no_ejecutable","agenda":sorted(agenda,key=lambda x:(x["proxima_fecha"],x["plan_id"])),
       "costo_estimado_centavos":costo,"hallazgos":hallazgos,"aprobado":not hallazgos,"controles":{"ejecuciones":0,"movimientos_stock":0,"compras":0,"conexiones_externas":0}}
    r["huella_mantenimiento"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest();return r
def exportar_control(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode())
