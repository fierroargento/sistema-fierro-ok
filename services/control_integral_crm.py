"""Control final del CRM tenant basado exclusivamente en datos locales."""

import hashlib
import io
import json

from services.certificacion_offline_crm import certificar_crm


def controlar_crm(*, organizacion_id, modulo, unidades, etapas, clientes, identidades, oportunidades, actividades, lotes):
    certificacion = certificar_crm(
        organizacion_id=organizacion_id,
        modulo=modulo,
        unidades=unidades,
        etapas=etapas,
        clientes=clientes,
        identidades=identidades,
        oportunidades=oportunidades,
        actividades=actividades,
    )
    lotes_tenant = [x for x in lotes if x.organizacion_id == organizacion_id]
    inconsistencias = []
    huellas = set()
    for lote in lotes_tenant:
        if lote.huella_documento in huellas:
            inconsistencias.append({"codigo": "huella_lote_duplicada", "lote_id": lote.id})
        huellas.add(lote.huella_documento)
        if lote.automatizaciones is not False:
            inconsistencias.append({"codigo": "lote_con_automatizaciones", "lote_id": lote.id})
        if lote.estado not in {"confirmado", "anulado"}:
            inconsistencias.append({"codigo": "estado_lote_invalido", "lote_id": lote.id})
    resumen = {
        **certificacion["resumen"],
        "lotes": len(lotes_tenant),
        "lotes_confirmados": sum(x.estado == "confirmado" for x in lotes_tenant),
        "lotes_anulados": sum(x.estado == "anulado" for x in lotes_tenant),
        "inconsistencias_lotes": len(inconsistencias),
    }
    resultado = {
        "organizacion_id": organizacion_id,
        "modo": "offline",
        "aprobado": certificacion["aprobada"] and not inconsistencias,
        "resumen": resumen,
        "hallazgos_crm": certificacion["hallazgos"],
        "inconsistencias_lotes": inconsistencias,
        "controles": {
            "aislamiento_tenant": True,
            "trazabilidad_lotes": not inconsistencias,
            "pedidos_creados": 0,
            "mensajes_enviados": 0,
            "automatizaciones": False,
            "acciones_externas": 0,
            "escrituras": 0,
        },
    }
    resultado["huella_control"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_control(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
