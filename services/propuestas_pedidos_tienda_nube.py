"""Congela y decide propuestas TN sin crear pedidos operativos."""
import json
from services.fechas import ahora_utc_naive

DESTINOS={"aprobar":"aprobada","rechazar":"rechazada","archivar":"archivada"}

def crear_propuestas(plan,*,usuario,PropuestaPedidoTiendaNube,EventoPropuestaPedidoTiendaNube,db_session):
    if plan.get("puede_aplicar") or plan.get("escrituras") or plan.get("acciones_externas"):raise ValueError("El plan incumple el contrato de solo lectura.")
    tenant=plan["tenant"];lote=plan["lote"];creadas=[];repetidas=[]
    candidatas=[f for f in plan.get("filas",[]) if f.get("estado")=="preparado" and f.get("crearia_pedido")]
    if not candidatas:raise ValueError("El plan no contiene propuestas preparables.")
    try:
        for fila in candidatas:
            existente=PropuestaPedidoTiendaNube.query.filter_by(organizacion_id=tenant["organizacion_id"],unidad_negocio_id=tenant["unidad_negocio_id"],tienda_nube_cuenta_id=lote.get("cuenta_id"),tn_order_id=fila["order_id"]).first()
            if existente is not None:repetidas.append(existente);continue
            propuesta=PropuestaPedidoTiendaNube(organizacion_id=tenant["organizacion_id"],unidad_negocio_id=tenant["unidad_negocio_id"],tienda_nube_cuenta_id=lote["cuenta_id"],lote_diagnostico_id=lote["id"],tn_order_id=fila["order_id"],tn_order_number=fila.get("numero"),snapshot_json=json.dumps(fila,ensure_ascii=False,sort_keys=True),firma_plan=plan["firma_plan"],estado="preparada",puede_crear_pedido=False,creado_por_usuario_id=getattr(usuario,"id",None),creado_por_username=getattr(usuario,"username",None))
            db_session.add(propuesta);db_session.flush();db_session.add(EventoPropuestaPedidoTiendaNube(organizacion_id=propuesta.organizacion_id,unidad_negocio_id=propuesta.unidad_negocio_id,propuesta_id=propuesta.id,estado_anterior=None,estado_nuevo="preparada",motivo="Propuesta generada desde plan simulado",username=getattr(usuario,"username",None)));creadas.append(propuesta)
        db_session.commit()
    except Exception:db_session.rollback();raise
    return {"creadas":creadas,"repetidas":repetidas,"acciones_externas":0,"pedidos_creados":0}

def decidir_propuestas(propuestas,accion,motivo,*,organizacion_id,unidad_negocio_id,usuario,EventoPropuestaPedidoTiendaNube,db_session):
    accion=str(accion or "").strip().lower();razon=str(motivo or "").strip()
    if accion not in DESTINOS:raise ValueError("La decision masiva no es valida.")
    if accion in {"rechazar","archivar"} and not razon:raise ValueError("La decision requiere un motivo.")
    seleccion=list(propuestas or [])
    if not seleccion:raise ValueError("Selecciona al menos una propuesta.")
    destino=DESTINOS[accion]
    try:
        for propuesta in seleccion:
            if propuesta.organizacion_id!=organizacion_id or propuesta.unidad_negocio_id!=unidad_negocio_id:raise ValueError("Una propuesta no pertenece a la unidad activa.")
            permitidos={"preparada"} if accion in {"aprobar","rechazar"} else {"aprobada","rechazada"}
            if propuesta.estado not in permitidos or propuesta.puede_crear_pedido:raise ValueError("Una propuesta no admite la transicion solicitada.")
        for propuesta in seleccion:
            anterior=propuesta.estado;propuesta.estado=destino;propuesta.puede_crear_pedido=False;propuesta.motivo=razon or None;propuesta.decidido_por_usuario_id=getattr(usuario,"id",None);propuesta.decidido_por_username=getattr(usuario,"username",None);propuesta.fecha_decision=ahora_utc_naive();db_session.add(EventoPropuestaPedidoTiendaNube(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,propuesta_id=propuesta.id,estado_anterior=anterior,estado_nuevo=destino,motivo=razon or None,username=getattr(usuario,"username",None)))
        db_session.commit()
    except Exception:db_session.rollback();raise
    return {"actualizadas":len(seleccion),"estado":destino,"acciones_externas":0,"pedidos_creados":0}

def resumir_propuestas(propuestas,*,organizacion_id,unidad_negocio_id):
    propias=[p for p in (propuestas or []) if p.organizacion_id==organizacion_id and p.unidad_negocio_id==unidad_negocio_id];propias.sort(key=lambda p:(p.fecha_creacion,p.id),reverse=True)
    return {"filas":propias,"total":len(propias),"preparadas":sum(p.estado=="preparada" for p in propias),"aprobadas":sum(p.estado=="aprobada" for p in propias),"rechazadas":sum(p.estado=="rechazada" for p in propias),"pedidos_creados":0,"acciones_externas":0}
