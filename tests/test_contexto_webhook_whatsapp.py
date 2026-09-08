import pytest

from services.contexto_webhook_whatsapp import (
    ContextoWebhookWhatsAppError,
    extraer_phone_number_id,
    resolver_contexto_webhook_whatsapp,
)


def payload(numero="wa-123"):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": numero}
    }}]}]}


def test_extrae_identidad_de_cuenta_desde_evento():
    assert extraer_phone_number_id(payload()) == "wa-123"


def test_resuelve_unico_vinculo_activo():
    contexto = resolver_contexto_webhook_whatsapp(payload(), [{
        "phone_number_id": "wa-123", "organizacion_id": 7,
        "unidad_negocio_id": 9, "estado": "activo",
    }])
    assert contexto == {
        "phone_number_id": "wa-123", "organizacion_id": 7,
        "unidad_negocio_id": 9,
    }


@pytest.mark.parametrize("vinculos", [[], [
    {"phone_number_id": "wa-123", "organizacion_id": 7,
     "unidad_negocio_id": 9, "estado": "desactivado"},
]])
def test_no_hay_fallback_global(vinculos):
    with pytest.raises(ContextoWebhookWhatsAppError, match="sin vínculo"):
        resolver_contexto_webhook_whatsapp(payload(), vinculos)


def test_rechaza_ambiguedad_entre_tenants():
    vinculos = [
        {"phone_number_id": "wa-123", "organizacion_id": 7,
         "unidad_negocio_id": 9, "estado": "activo"},
        {"phone_number_id": "wa-123", "organizacion_id": 8,
         "unidad_negocio_id": 10, "estado": "activo"},
    ]
    with pytest.raises(ContextoWebhookWhatsAppError, match="ambiguo"):
        resolver_contexto_webhook_whatsapp(payload(), vinculos)


def test_no_realiza_transporte_ni_persistencia():
    import inspect
    import services.contexto_webhook_whatsapp as modulo

    fuente = inspect.getsource(modulo)
    assert "requests" not in fuente
    assert "db.session" not in fuente
    assert "commit(" not in fuente
