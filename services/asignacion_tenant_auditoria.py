"""Flujo explícito para resolver auditorías legacy no ambiguas."""
import json

def obtener_propuestas_tenant(organizacion_id, *, AsignacionTenantAuditoria, limite=500):
    return (AsignacionTenantAuditoria.query.filter_by(organizacion_propuesta_id=int(organizacion_id)).order_by(AsignacionTenantAuditoria.id.desc()).limit(max(1,min(int(limite),1000))).all())

def preparar_propuestas(diagnostico, *, organizacion_id, AsignacionTenantAuditoria, Auditoria, db_session, usuario):
    existentes={x.auditoria_id for x in AsignacionTenantAuditoria.query.all()};auditorias={x.id:x for x in Auditoria.query.filter(Auditoria.organizacion_id.is_(None)).all()};nuevas=[]
    for item in diagnostico.get("auditorias",[]):
        aid=item.get("auditoria_id");oid=item.get("organizacion_propuesta_id")
        if item.get("estado")!="asignable" or oid!=organizacion_id or aid in existentes or aid not in auditorias:continue
        nuevas.append(AsignacionTenantAuditoria(auditoria_id=aid,organizacion_propuesta_id=oid,estado="preparada",evidencia_json=json.dumps(item,ensure_ascii=False,sort_keys=True),preparado_por=getattr(usuario,"username",None) or "admin"));existentes.add(aid)
    if nuevas:db_session.add_all(nuevas);db_session.commit()
    return len(nuevas)

def obtener_propuesta(propuesta_id, *, AsignacionTenantAuditoria):
    propuesta=AsignacionTenantAuditoria.query.filter_by(id=int(propuesta_id)).first()
    if propuesta is None:raise ValueError("La propuesta de auditoría no existe.")
    return propuesta

def aprobar_propuesta(propuesta, *, usuario, db_session):
    if propuesta.estado!="preparada":raise ValueError("La propuesta ya no está preparada.")
    if propuesta.auditoria.organizacion_id is not None:raise ValueError("La auditoría ya tiene tenant.")
    propuesta.estado="aprobada";propuesta.aprobado_por=getattr(usuario,"username",None) or "admin";db_session.commit();return propuesta

def rechazar_propuesta(propuesta, *, motivo, usuario, db_session):
    if propuesta.estado not in {"preparada","aprobada"}:raise ValueError("La propuesta ya no puede rechazarse.")
    propuesta.estado="rechazada";propuesta.motivo_rechazo=str(motivo or "Rechazada por el administrador.").strip()[:300];propuesta.aprobado_por=getattr(usuario,"username",None) or "admin";db_session.commit();return propuesta

def aplicar_propuesta(propuesta, *, confirmacion, usuario, db_session):
    if confirmacion!="ASIGNAR TENANT":raise ValueError("Escribí ASIGNAR TENANT para confirmar.")
    if propuesta.estado!="aprobada":raise ValueError("La propuesta debe estar aprobada.")
    auditoria=propuesta.auditoria
    if auditoria.organizacion_id is not None:raise ValueError("La auditoría ya tiene tenant.")
    evidencia=json.loads(propuesta.evidencia_json)
    if evidencia.get("estado")!="asignable" or evidencia.get("organizacion_propuesta_id")!=propuesta.organizacion_propuesta_id:raise ValueError("La evidencia de asignación no coincide.")
    auditoria.organizacion_id=propuesta.organizacion_propuesta_id;propuesta.estado="aplicada";propuesta.aplicado_por=getattr(usuario,"username",None) or "admin";db_session.commit();return propuesta
