"""Certifica en memoria la frontera tenant de eventos WhatsApp."""

import json
from io import BytesIO

from services.procesador_offline_whatsapp import procesar_payload_whatsapp_offline


def _payload(*, phone="PHONE-A", messages=None, statuses=None):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone},
        "messages": messages or [],
        "statuses": statuses or [],
    }}]}]}


def escenarios_certificacion_whatsapp():
    vinculo_a = {
        "whatsapp_phone_number_id": "PHONE-A",
        "organizacion_id": 1, "unidad_negocio_id": 10, "estado": "activo",
    }
    mensaje = {
        "id": "wamid.cert.1", "from": "5492920000000", "type": "text",
        "text": {"body": "Prueba"}, "timestamp": "100",
    }
    return [
        {
            "codigo": "tenant_valido", "descripcion": "Cuenta activa e identidad completa",
            "payload": _payload(messages=[mensaje]), "vinculos": [vinculo_a],
            "esperado": {"procesados": 1, "duplicados": 0, "errores": 0},
        },
        {
            "codigo": "cuenta_desconocida", "descripcion": "Sin fallback a otro tenant",
            "payload": _payload(phone="PHONE-X", messages=[mensaje]), "vinculos": [vinculo_a],
            "esperado": {"procesados": 0, "duplicados": 0, "errores": 1},
        },
        {
            "codigo": "tenant_ambiguo", "descripcion": "Dos vinculos activos con la misma cuenta",
            "payload": _payload(messages=[mensaje]),
            "vinculos": [vinculo_a, {**vinculo_a, "organizacion_id": 2}],
            "esperado": {"procesados": 0, "duplicados": 0, "errores": 1},
        },
        {
            "codigo": "mensaje_duplicado", "descripcion": "Una referencia se procesa una sola vez",
            "payload": _payload(messages=[mensaje, mensaje]), "vinculos": [vinculo_a],
            "esperado": {"procesados": 1, "duplicados": 1, "errores": 0},
        },
        {
            "codigo": "estados_desordenados", "descripcion": "Los estados se preservan sin mutar historial",
            "payload": _payload(statuses=[
                {"id": "wamid.out", "status": "read", "timestamp": "103"},
                {"id": "wamid.out", "status": "sent", "timestamp": "101"},
                {"id": "wamid.out", "status": "delivered", "timestamp": "102"},
            ]),
            "vinculos": [vinculo_a],
            "esperado": {"procesados": 3, "duplicados": 0, "errores": 0},
        },
        {
            "codigo": "payload_invalido", "descripcion": "Mensaje sin identidad id/remitente",
            "payload": _payload(messages=[{"type": "text"}]), "vinculos": [vinculo_a],
            "esperado": {"procesados": 0, "duplicados": 0, "errores": 1},
        },
    ]


def certificar_escenarios_whatsapp(escenarios=None):
    resultados = []
    for escenario in escenarios or escenarios_certificacion_whatsapp():
        obtenido = procesar_payload_whatsapp_offline(
            escenario["payload"], escenario["vinculos"],
        )
        resumen = obtenido["resumen"]
        esperado = escenario["esperado"]
        cumple = resumen == esperado
        resultados.append({
            "codigo": escenario["codigo"],
            "descripcion": escenario["descripcion"],
            "cumple": cumple,
            "esperado": esperado,
            "obtenido": resumen,
            "errores": obtenido["errores"],
        })
    return {
        "aprobada": all(item["cumple"] for item in resultados),
        "total": len(resultados),
        "aprobados": sum(item["cumple"] for item in resultados),
        "rechazados": sum(not item["cumple"] for item in resultados),
        "resultados": resultados,
        "escrituras": 0,
        "acciones_externas": 0,
    }


def exportar_certificacion_whatsapp(resultado):
    salida = BytesIO(json.dumps(
        resultado, ensure_ascii=False, sort_keys=True, indent=2,
    ).encode("utf-8"))
    salida.seek(0)
    return salida
