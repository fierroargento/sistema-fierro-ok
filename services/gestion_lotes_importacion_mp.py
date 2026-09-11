"""Revision y anulacion interna de lotes MP, sin borrar ni devolver dinero."""
import json

def _referencias(lote):
    try: vista=json.loads(lote.evidencia_json or "{}")
    except (TypeError,ValueError): raise ValueError("La evidencia del lote no es legible.")
    return {(f["datos"]["cuenta_codigo"],f["datos"]["referencia_movimiento"]) for f in vista.get("filas",[]) if f.get("accion")=="crear"}

def diagnosticar_lote(lote,movimientos,*,organizacion_id,unidad_negocio_id):
    if lote is None or lote.organizacion_id!=organizacion_id or lote.unidad_negocio_id!=unidad_negocio_id: raise ValueError("El lote no pertenece a la unidad activa.")
    referencias=_referencias(lote);propios=[m for m in (movimientos or []) if m.organizacion_id==organizacion_id and m.unidad_negocio_id==unidad_negocio_id and (m.cuenta_codigo,m.referencia_movimiento) in referencias]
    encontrados={(m.cuenta_codigo,m.referencia_movimiento) for m in propios};faltantes=sorted(referencias-encontrados)
    ajenos=[m.referencia_movimiento for m in propios if m.origen!="extracto_mp"]
    anulados=[m.referencia_movimiento for m in propios if m.estado=="anulado"]
    bloqueos=[]
    if lote.estado!="confirmado":bloqueos.append("El lote ya no esta confirmado.")
    if faltantes:bloqueos.append(f"Faltan {len(faltantes)} movimientos del lote.")
    if ajenos:bloqueos.append("Hay movimientos cuyo origen no es el extracto MP.")
    if anulados:bloqueos.append("Hay movimientos que ya estaban anulados.")
    return {"lote":lote,"movimientos":propios,"esperados":len(referencias),"encontrados":len(propios),"bloqueos":bloqueos,"anulable":not bloqueos,"acciones_externas":0,"eliminaciones":0}

def anular_lote(lote,movimientos,motivo,*,organizacion_id,unidad_negocio_id,db_session):
    razon=str(motivo or "").strip()
    if not razon:raise ValueError("El motivo de anulacion es obligatorio.")
    diagnostico=diagnosticar_lote(lote,movimientos,organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id)
    if not diagnostico["anulable"]:raise ValueError("El lote no puede anularse: "+" ".join(diagnostico["bloqueos"]))
    try:
        for movimiento in diagnostico["movimientos"]:
            movimiento.estado="anulado";movimiento.detalle=((movimiento.detalle or "")+f" | Lote anulado internamente: {razon}")[:500]
        lote.estado="anulado";db_session.commit()
    except Exception:db_session.rollback();raise
    return {"lote_id":lote.id,"movimientos_anulados":len(diagnostico["movimientos"]),"motivo":razon,"acciones_externas":0,"eliminaciones":0}

def construir_historial(lotes,movimientos,*,organizacion_id,unidad_negocio_id):
    propios=[l for l in (lotes or []) if l.organizacion_id==organizacion_id and l.unidad_negocio_id==unidad_negocio_id];propios.sort(key=lambda l:(l.fecha_creacion,l.id),reverse=True)
    return {"filas":[diagnosticar_lote(l,movimientos,organizacion_id=organizacion_id,unidad_negocio_id=unidad_negocio_id) for l in propios],"total":len(propios),"confirmados":sum(l.estado=="confirmado" for l in propios),"anulados":sum(l.estado=="anulado" for l in propios),"acciones_externas":0}
