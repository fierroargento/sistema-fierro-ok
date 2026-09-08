import json
from pathlib import Path

from services.procesador_offline_whatsapp import (
    procesar_documento_whatsapp_offline,
    procesar_payload_whatsapp_offline,
)


VINCULOS = [{
    "whatsapp_phone_number_id": "PHONE-1",
    "organizacion_id": 10,
    "unidad_negocio_id": 20,
    "estado": "activo",
}]


def payload(messages=None, statuses=None, phone="PHONE-1"):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone},
        "messages": messages or [], "statuses": statuses or [],
    }}]}]}


def test_normaliza_mensaje_con_identidad_tenant():
    resultado = procesar_payload_whatsapp_offline(payload(messages=[{
        "id": "wamid.1", "from": "5492920123456", "type": "text",
        "text": {"body": "Hola"}, "timestamp": "1",
    }]), VINCULOS)
    sobre = resultado["sobres"][0]
    assert sobre["organizacion_id"] == 10
    assert sobre["unidad_negocio_id"] == 20
    assert sobre["referencia"] == "wamid.1:in"
    assert sobre["datos"]["texto"] == "Hola"


def test_normaliza_estado_sin_actualizar_historial():
    resultado = procesar_payload_whatsapp_offline(payload(statuses=[{
        "id": "wamid.out", "status": "delivered", "timestamp": "2",
    }]), VINCULOS)
    assert resultado["sobres"][0]["tipo"] == "estado_mensaje"
    assert resultado["sobres"][0]["datos"]["estado_meta"] == "delivered"
    assert resultado["escrituras"] == 0


def test_deduplica_en_lote_y_con_referencias_previas():
    mensaje = {"id": "wamid.1", "from": "549", "type": "text"}
    documento = payload(messages=[mensaje, mensaje])
    resultado = procesar_payload_whatsapp_offline(
        documento, VINCULOS, referencias_vistas={"anterior:in"},
    )
    assert resultado["resumen"] == {"procesados": 1, "duplicados": 1, "errores": 0}


def test_aisla_cuenta_desconocida_sin_fallback_global():
    resultado = procesar_payload_whatsapp_offline(
        payload(messages=[{"id": "x", "from": "549", "type": "text"}], phone="OTRA"),
        VINCULOS,
    )
    assert resultado["sobres"] == []
    assert resultado["resumen"]["errores"] == 1


def test_documento_utf8_y_huella_son_deterministas():
    datos = payload(messages=[{
        "id": "wamid.2", "from": "549", "type": "text",
        "text": {"body": "Información"},
    }])
    primero = procesar_documento_whatsapp_offline(
        json.dumps(datos, ensure_ascii=False).encode("utf-8"), VINCULOS,
    )["sobres"][0]
    segundo = procesar_payload_whatsapp_offline(datos, VINCULOS)["sobres"][0]
    assert primero["payload_hash"] == segundo["payload_hash"]


def test_servicio_no_tiene_transporte_persistencia_ni_secretos():
    fuente = Path("services/procesador_offline_whatsapp.py").read_text(
        encoding="utf-8"
    ).lower()
    for prohibido in (
        "requests", "urlopen", "db.session", "commit(", "access_token",
        "app_secret", "wa_verify_token", "http://", "https://",
    ):
        assert prohibido not in fuente
    productivo = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8")
    assert "procesador_offline_whatsapp" not in productivo
