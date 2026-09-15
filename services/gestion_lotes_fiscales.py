"""Historial y anulación interna de lotes fiscales; nunca emite ni conecta."""

import io
import json


def listar_lotes(LoteImportacionFiscal, *, organizacion_id, limite=100):
    limite = max(1, min(int(limite or 100), 200))
    return (
        LoteImportacionFiscal.query
        .filter_by(organizacion_id=organizacion_id)
        .order_by(LoteImportacionFiscal.fecha_creacion.desc(), LoteImportacionFiscal.id.desc())
        .limit(limite).all()
    )


def obtener_lote(LoteImportacionFiscal, *, organizacion_id, lote_id):
    lote = LoteImportacionFiscal.query.filter_by(id=lote_id, organizacion_id=organizacion_id).first()
    if lote is None:
        raise ValueError("No se encontró el lote fiscal dentro del tenant.")
    return lote


def _evidencia(lote):
    try:
        documento = json.loads(lote.evidencia_json or "{}")
    except json.JSONDecodeError as error:
        raise ValueError("La evidencia del lote fiscal está dañada.") from error
    comprobantes = documento.get("comprobantes")
    if not isinstance(comprobantes, list):
        raise ValueError("La evidencia del lote fiscal está incompleta.")
    return documento


def referencias_lote(lote):
    return [str(c.get("referencia") or "") for c in _evidencia(lote)["comprobantes"] if c.get("referencia")]


def exportar_lote(lote):
    documento = {
        "lote_id": lote.id, "organizacion_id": lote.organizacion_id,
        "nombre_archivo": lote.nombre_archivo, "huella_documento": lote.huella_documento,
        "huella_plan": lote.huella_plan, "estado": lote.estado,
        "comprobantes_creados": lote.comprobantes_creados, "items_creados": lote.items_creados,
        "rechazados": lote.rechazados, "emision_real": False,
        "creado_por": lote.creado_por_username, "fecha_creacion": lote.fecha_creacion,
        "evidencia": _evidencia(lote),
    }
    return io.BytesIO(json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))


def anular_lote(lote, *, motivo, usuario, BorradorComprobanteFiscal, EventoFiscal, db_session):
    motivo = str(motivo or "").strip()
    if lote is None or lote.estado != "confirmado":
        raise ValueError("El lote fiscal no está disponible para anulación.")
    if not motivo:
        raise ValueError("Indicá el motivo de la anulación.")
    referencias = referencias_lote(lote)
    if not referencias:
        raise ValueError("El lote no contiene referencias fiscales auditables.")
    borradores = (
        BorradorComprobanteFiscal.query
        .filter_by(organizacion_id=lote.organizacion_id)
        .filter(BorradorComprobanteFiscal.referencia_externa.in_(referencias)).all()
    )
    encontrados = {b.referencia_externa for b in borradores}
    if encontrados != set(referencias):
        raise ValueError("No se encontraron todos los borradores del lote dentro del tenant.")
    if any(b.estado == "autorizado" or b.cae or b.numero_autorizado for b in borradores):
        raise ValueError("El lote contiene un comprobante autorizado y no puede anularse internamente.")
    if any(b.estado not in {"borrador", "listo", "cancelado"} for b in borradores):
        raise ValueError("El lote contiene un estado fiscal incompatible.")
    try:
        nombre_usuario = str(getattr(usuario, "username", None) or "admin")[:100]
        for borrador in borradores:
            anterior = borrador.estado
            borrador.estado = "cancelado"
            db_session.add(EventoFiscal(
                organizacion_id=lote.organizacion_id, borrador_comprobante_fiscal_id=borrador.id,
                tipo="lote_importacion_anulado", detalle=f"Estado anterior: {anterior}. Motivo: {motivo[:1500]}",
                referencia_externa=borrador.referencia_externa, usuario=nombre_usuario,
            ))
        evidencia = _evidencia(lote)
        evidencia["anulacion"] = {"motivo": motivo[:1500], "usuario": nombre_usuario, "borradores_cancelados": len(borradores), "acciones_externas": 0}
        lote.evidencia_json = json.dumps(evidencia, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        lote.estado = "anulado"
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return {"lote_id": lote.id, "borradores_cancelados": len(borradores), "estado": lote.estado}
