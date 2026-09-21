"""Turnos y novedades internas sin fichaje ni nomina."""
import hashlib,io,json
from collections import defaultdict
from datetime import date,datetime

def _validar_empleado(e,org,unidad):
    if e is None or e.tipo_registro!="empleado" or int(e.organizacion_id)!=int(org) or int(e.unidad_negocio_id)!=int(unidad):raise ValueError("El empleado no pertenece al contexto activo.")
def crear_turno(datos,*,empleado,organizacion_id,unidad_negocio_id,Turno,db_session,usuario_id=None):
    _validar_empleado(empleado,organizacion_id,unidad_negocio_id)
    try:inicio=datetime.fromisoformat(str(datos.get("inicio") or ""));fin=datetime.fromisoformat(str(datos.get("fin") or ""))
    except ValueError:raise ValueError("Inicio o fin invalido.")
    if fin<=inicio or (fin-inicio).total_seconds()>16*3600:raise ValueError("El turno debe durar entre cero y dieciseis horas.")
    sector=str(datos.get("sector") or empleado.sector or "").strip();tarea=str(datos.get("tarea") or "").strip()
    if not sector:raise ValueError("El sector es obligatorio.")
    base=f"{organizacion_id}:{unidad_negocio_id}:{empleado.id}:{inicio.isoformat()}:{fin.isoformat()}:{sector}:{tarea}"
    t=Turno(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,empleado_id=empleado.id,inicio=inicio,fin=fin,sector=sector,tarea=tarea or None,clave_idempotencia=hashlib.sha256(base.encode()).hexdigest(),estado="planificado",confirmado=False,afecta_nomina=False,creado_por_usuario_id=usuario_id)
    db_session.add(t);db_session.commit();return t
def crear_novedad(datos,*,empleado,organizacion_id,unidad_negocio_id,Novedad,db_session,usuario_id=None):
    _validar_empleado(empleado,organizacion_id,unidad_negocio_id);tipo=str(datos.get("tipo") or "").strip();detalle=str(datos.get("detalle") or "").strip()
    if tipo not in {"licencia","ausencia","horas_extra","observacion"} or not detalle:raise ValueError("Tipo y detalle de novedad invalidos.")
    try:desde=date.fromisoformat(str(datos.get("fecha_desde") or ""));hasta=date.fromisoformat(str(datos.get("fecha_hasta") or ""));minutos=int(datos.get("minutos_propuestos") or 0)
    except ValueError:raise ValueError("Fechas o minutos invalidos.")
    if hasta<desde or minutos<0:raise ValueError("El rango o los minutos no son validos.")
    if tipo!="horas_extra" and minutos:raise ValueError("Solo las horas extra admiten minutos propuestos.")
    base=f"{organizacion_id}:{unidad_negocio_id}:{empleado.id}:{tipo}:{desde}:{hasta}:{minutos}:{detalle}"
    n=Novedad(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,empleado_id=empleado.id,tipo=tipo,fecha_desde=desde,fecha_hasta=hasta,detalle=detalle,minutos_propuestos=minutos,clave_idempotencia=hashlib.sha256(base.encode()).hexdigest(),estado="propuesta",aprobada=False,afecta_nomina=False,creado_por_usuario_id=usuario_id)
    db_session.add(n);db_session.commit();return n
def cancelar(objeto,*,organizacion_id,unidad_negocio_id,motivo,db_session):
    if int(objeto.organizacion_id)!=int(organizacion_id) or int(objeto.unidad_negocio_id)!=int(unidad_negocio_id) or objeto.estado not in {"planificado","propuesta"}:raise ValueError("El registro no puede cancelarse.")
    if getattr(objeto,"confirmado",False) or getattr(objeto,"aprobada",False) or objeto.afecta_nomina:raise ValueError("El registro tiene impacto incompatible.")
    motivo=str(motivo or "").strip()
    if len(motivo)<5:raise ValueError("El motivo debe tener al menos cinco caracteres.")
    objeto.estado="cancelado";objeto.observacion=f"CANCELADO: {motivo}";db_session.commit();return objeto
def controlar_personas(*,organizacion_id,unidad_negocio_id,empleados,turnos,novedades):
    ids={int(e.id) for e in empleados if e.tipo_registro=="empleado" and int(e.organizacion_id)==int(organizacion_id) and int(e.unidad_negocio_id)==int(unidad_negocio_id)};hallazgos=[];agenda=defaultdict(lambda:{"turnos":0,"minutos":0})
    por_empleado=defaultdict(list)
    for t in turnos:
        if int(t.organizacion_id)!=int(organizacion_id) or int(t.unidad_negocio_id)!=int(unidad_negocio_id):continue
        if int(t.empleado_id) not in ids:hallazgos.append({"codigo":"empleado_invalido","turno_id":t.id});continue
        if t.confirmado or t.afecta_nomina:hallazgos.append({"codigo":"turno_con_impacto","turno_id":t.id});continue
        if t.estado=="planificado":por_empleado[int(t.empleado_id)].append(t);clave=t.inicio.date().isoformat();agenda[clave]["turnos"]+=1;agenda[clave]["minutos"]+=int((t.fin-t.inicio).total_seconds()/60)
    for empleado_id,filas in por_empleado.items():
        filas.sort(key=lambda x:x.inicio)
        for anterior,actual in zip(filas,filas[1:]):
            if actual.inicio<anterior.fin:hallazgos.append({"codigo":"turnos_superpuestos","empleado_id":empleado_id,"turnos":[anterior.id,actual.id]})
    for n in novedades:
        if int(n.organizacion_id)==int(organizacion_id) and int(n.unidad_negocio_id)==int(unidad_negocio_id) and (n.aprobada or n.afecta_nomina):hallazgos.append({"codigo":"novedad_con_impacto","novedad_id":n.id})
    r={"organizacion_id":int(organizacion_id),"unidad_negocio_id":int(unidad_negocio_id),"modo":"personas_preparatorio_no_liquidable","agenda":[{"fecha":k,**v} for k,v in sorted(agenda.items())],"hallazgos":hallazgos,"aprobado":not hallazgos,"controles":{"fichajes":0,"liquidaciones":0,"costos_modificados":0,"conexiones_externas":0}}
    r["huella_personas"]=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(",",":")).encode()).hexdigest();return r
def exportar_control(r):return io.BytesIO(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2).encode())
