"""Versiona y decide cierres MP internos; no cobra, devuelve ni transfiere."""

import hashlib, io, json
from services.certificacion_offline_mercado_pago import certificar_conciliacion_mp
from services.conciliacion_liquidaciones_canal import construir_conciliaciones, incorporar_gestiones
from services.fechas import ahora_utc_naive


def _json(d): return json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)


def snapshot_conciliacion(ventas,movimientos,gestiones):
    ventas=list(ventas or []);movimientos=list(movimientos or []);gestiones=list(gestiones or [])
    filas,resumen=construir_conciliaciones(ventas,movimientos);incorporar_gestiones(filas,gestiones)
    datos=[]
    for f in filas:
        datos.append({"cuenta":f["cuenta_codigo"],"venta":f["referencia_venta"],"esperado":f["liquidacion_esperada_centavos"],"real":f["liquidacion_real_centavos"],"diferencia":f["diferencia_centavos"],"conciliacion":f["estado_conciliacion"],"economico":f["estado_economico"],"gestion":f["estado_gestion"]})
    return {"filas":datos,"resumen":resumen,"ventas_ids":sorted(getattr(x,"id",0) for x in ventas),"movimientos_ids":sorted(getattr(x,"id",0) for x in movimientos),"gestiones_ids":sorted(getattr(x,"id",0) for x in gestiones)}


def huella_snapshot(snapshot): return hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest()


def registrar_cierre(ventas,movimientos,gestiones,*,organizacion_id,unidad_negocio_id,usuario,CierreConciliacionMP,EventoCierreConciliacionMP,db_session):
    cert=certificar_conciliacion_mp(ventas,movimientos,gestiones,organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id)
    snap=snapshot_conciliacion(ventas,movimientos,gestiones);huella=huella_snapshot(snap)
    existente=CierreConciliacionMP.query.filter_by(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,huella_origen=huella).first()
    if existente:return existente,False
    cierre=CierreConciliacionMP(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,huella_origen=huella,snapshot_json=_json(snap),certificacion_json=_json(cert),estado="preparado",puede_ejecutar=False,creado_por_username=getattr(usuario,"username",None))
    db_session.add(cierre);db_session.flush();db_session.add(EventoCierreConciliacionMP(organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id,cierre_id=cierre.id,estado_anterior=None,estado_nuevo="preparado",motivo="Snapshot local de conciliacion",username=getattr(usuario,"username",None)));db_session.commit();return cierre,True


def decidir_cierre(cierre,accion,motivo,*,usuario,snapshot_actual,EventoCierreConciliacionMP,db_session):
    if cierre is None or cierre.puede_ejecutar:raise ValueError("El cierre no cumple el contrato interno.")
    mapa={"enviar_revision":({"preparado"},"revision"),"aprobar":({"revision"},"aprobado"),"cerrar":({"aprobado"},"cerrado"),"archivar":({"preparado","obsoleto","cerrado"},"archivado")}
    if accion not in mapa:raise ValueError("La decision no es valida.")
    origenes,destino=mapa[accion]
    if cierre.estado not in origenes:raise ValueError("La transicion no corresponde.")
    vigente=huella_snapshot(snapshot_actual)==cierre.huella_origen
    razon=str(motivo or "").strip();anterior=cierre.estado
    if accion in {"enviar_revision","aprobar","cerrar"} and not vigente:destino="obsoleto";razon=razon or "Los datos de conciliacion cambiaron."
    if accion in {"cerrar","archivar"} and not razon:raise ValueError("El cierre requiere motivo o comprobante.")
    if accion=="aprobar" and not json.loads(cierre.certificacion_json).get("aprobada"):raise ValueError("Una certificacion bloqueada no puede aprobarse.")
    cierre.estado=destino;cierre.motivo=razon or None;cierre.decidido_por_username=getattr(usuario,"username",None);cierre.fecha_decision=ahora_utc_naive();cierre.puede_ejecutar=False
    db_session.add(EventoCierreConciliacionMP(organizacion_id=cierre.organizacion_id,unidad_negocio_id=cierre.unidad_negocio_id,cierre_id=cierre.id,estado_anterior=anterior,estado_nuevo=destino,motivo=razon or None,username=getattr(usuario,"username",None)));db_session.commit();return {"cierre":cierre,"vigente":vigente,"estado":destino,"puede_ejecutar":False}


def exportar_cierre(cierre):
    return io.BytesIO(json.dumps({"id":cierre.id,"estado":cierre.estado,"puede_ejecutar":False,"snapshot":json.loads(cierre.snapshot_json),"certificacion":json.loads(cierre.certificacion_json),"eventos":[{"anterior":e.estado_anterior,"nuevo":e.estado_nuevo,"motivo":e.motivo,"usuario":e.username,"fecha":e.fecha_evento} for e in getattr(cierre,"eventos",[]) or []]},ensure_ascii=False,indent=2,default=str).encode("utf-8"))
