"""Gestión interna de lotes CRM confirmados, sin borrado ni efectos externos."""

import io
import json


def obtener_lote_tenant(lote_id, *, organizacion_id, LoteImportacionCRM):
    lote = (
        LoteImportacionCRM.query
        .filter(
            LoteImportacionCRM.id == int(lote_id),
            LoteImportacionCRM.organizacion_id == int(organizacion_id),
        )
        .first()
    )
    if lote is None:
        raise ValueError("El lote CRM no pertenece al tenant activo.")
    return lote


def exportar_evidencia(lote):
    try:
        evidencia = json.loads(lote.evidencia_json)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("La evidencia del lote CRM no es válida.") from error
    documento = {
        "lote_id": lote.id,
        "organizacion_id": lote.organizacion_id,
        "estado": lote.estado,
        "nombre_archivo": lote.nombre_archivo,
        "huella_documento": lote.huella_documento,
        "huella_plan": lote.huella_plan,
        "conteos": {
            "clientes": lote.clientes_creados,
            "identidades": lote.identidades_creadas,
            "oportunidades": lote.oportunidades_creadas,
            "actividades": lote.actividades_creadas,
        },
        "automatizaciones": False,
        "evidencia": evidencia,
    }
    return io.BytesIO(json.dumps(documento, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))


def anular_lote(lote, *, organizacion_id, db_session):
    """Anula el expediente; conserva todos los registros y su trazabilidad."""
    if lote.organizacion_id != int(organizacion_id):
        raise ValueError("El lote CRM no pertenece al tenant activo.")
    if lote.estado != "confirmado":
        raise ValueError("El lote CRM ya no está confirmado.")
    if lote.automatizaciones is not False:
        raise ValueError("El lote no cumple el contrato desconectado.")
    lote.estado = "anulado"
    db_session.commit()
    return lote
