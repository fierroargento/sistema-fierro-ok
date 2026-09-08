"""Ensaya el motor WhatsApp tenant en sombra, sin ejecutar efectos."""

import hashlib
import json
from io import BytesIO

from services.procesador_offline_whatsapp import procesar_payload_whatsapp_offline


BLOQUEOS_SOMBRA = {
    "recepcion_externa": False,
    "persistencia": False,
    "respuestas": False,
    "mensajes_salientes": False,
    "actualizacion_estados": False,
}


def _firma(items):
    canonico = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def proyectar_decisiones_sombra(sobres):
    decisiones = []
    for sobre in sobres or []:
        datos = sobre.get("datos") or {}
        if sobre.get("tipo") == "mensaje_entrante":
            accion = "evaluar_enrutamiento_sin_ejecutar"
        elif sobre.get("tipo") == "estado_mensaje":
            accion = "evaluar_transicion_sin_actualizar"
        else:
            accion = "ignorar_tipo_no_reconocido"
        decisiones.append({
            "referencia": sobre.get("referencia"),
            "organizacion_id": sobre.get("organizacion_id"),
            "unidad_negocio_id": sobre.get("unidad_negocio_id"),
            "accion_proyectada": accion,
            "tipo_mensaje": datos.get("tipo_mensaje"),
            "estado_meta": datos.get("estado_meta"),
            "ejecutada": False,
        })
    return decisiones


def comparar_resultados_sombra(decisiones, legado_observado=None):
    legado = legado_observado or []
    por_referencia = {str(item.get("referencia")): item for item in legado}
    diferencias = []
    for decision in decisiones:
        referencia = str(decision.get("referencia"))
        observado = por_referencia.pop(referencia, None)
        if observado is None:
            diferencias.append({
                "referencia": referencia, "codigo": "sin_observacion_legado",
                "detalle": "No se informo una observacion comparable del flujo actual.",
            })
            continue
        for campo in ("organizacion_id", "unidad_negocio_id", "accion_proyectada"):
            if observado.get(campo) != decision.get(campo):
                diferencias.append({
                    "referencia": referencia, "codigo": f"diferencia_{campo}",
                    "esperado": decision.get(campo), "observado": observado.get(campo),
                })
    for referencia in sorted(por_referencia):
        diferencias.append({
            "referencia": referencia, "codigo": "solo_en_legado",
            "detalle": "La observacion no tiene un evento normalizado equivalente.",
        })
    return diferencias


def evaluar_payload_en_sombra(payload, vinculos, *, referencias_vistas=None, legado_observado=None):
    normalizado = procesar_payload_whatsapp_offline(
        payload, vinculos, referencias_vistas,
    )
    decisiones = proyectar_decisiones_sombra(normalizado["sobres"])
    diferencias = comparar_resultados_sombra(decisiones, legado_observado)
    resultado = {
        "normalizado": normalizado,
        "decisiones": decisiones,
        "diferencias": diferencias,
        "resumen": {
            **normalizado["resumen"],
            "decisiones": len(decisiones),
            "diferencias": len(diferencias),
        },
        "bloqueos": dict(BLOQUEOS_SOMBRA),
        "modo": "sombra_desconectada",
        "aplicable": False,
    }
    resultado["firma_evidencia"] = _firma({
        "resumen": resultado["resumen"],
        "decisiones": decisiones,
        "diferencias": diferencias,
    })
    return resultado


def evaluar_lote_en_sombra(documentos, vinculos, *, legado_por_documento=None):
    resultados = []
    errores = []
    vistos = set()
    legado_por_documento = legado_por_documento or {}
    for posicion, payload in enumerate(documentos or [], start=1):
        try:
            resultado = evaluar_payload_en_sombra(
                payload, vinculos, referencias_vistas=vistos,
                legado_observado=legado_por_documento.get(posicion),
            )
            vistos.update(
                sobre["referencia"] for sobre in resultado["normalizado"]["sobres"]
            )
            resultados.append({"posicion": posicion, "resultado": resultado})
        except (ValueError, TypeError) as error:
            errores.append({"posicion": posicion, "error": str(error)})
    return {
        "resultados": resultados,
        "errores": errores,
        "resumen": {
            "documentos": len(documentos or []),
            "procesados": len(resultados),
            "errores": len(errores),
            "eventos": sum(
                item["resultado"]["resumen"]["procesados"] for item in resultados
            ),
        },
        "bloqueos": dict(BLOQUEOS_SOMBRA),
        "acciones_externas": 0,
        "escrituras": 0,
    }


def matriz_preparacion_sombra(vinculos, certificacion):
    registros = list(vinculos or [])
    phone_ids = [
        str(getattr(item, "whatsapp_phone_number_id", None)
            or (item.get("whatsapp_phone_number_id") if isinstance(item, dict) else "")
            or "").strip()
        for item in registros
    ]
    controles = [
        ("cuenta_registrada", bool(registros)),
        ("phone_number_id_completo", bool(phone_ids) and all(phone_ids)),
        ("phone_number_id_unico", len(phone_ids) == len(set(phone_ids))),
        ("certificacion_offline", bool(certificacion.get("aprobada"))),
        ("recepcion_externa_bloqueada", not BLOQUEOS_SOMBRA["recepcion_externa"]),
        ("persistencia_bloqueada", not BLOQUEOS_SOMBRA["persistencia"]),
        ("respuestas_bloqueadas", not BLOQUEOS_SOMBRA["respuestas"]),
    ]
    detalle = [{"clave": clave, "cumple": cumple} for clave, cumple in controles]
    return {
        "detalle": detalle,
        "apta_para_ensayo_manual": all(item["cumple"] for item in detalle),
        "apta_para_conexion": False,
        "faltantes": [item["clave"] for item in detalle if not item["cumple"]],
    }


def exportar_evidencia_sombra(resultado):
    salida = BytesIO(json.dumps(
        resultado, ensure_ascii=False, sort_keys=True, indent=2,
    ).encode("utf-8"))
    salida.seek(0)
    return salida
