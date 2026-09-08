from pathlib import Path

import pytest

from services.contexto_webhook_whatsapp import resolver_contexto_webhook_whatsapp
from services.vinculos_canales import validar_cuenta_exclusiva


def test_vinculo_whatsapp_exige_phone_number_id():
    with pytest.raises(ValueError, match="phone_number_id"):
        validar_cuenta_exclusiva("whatsapp")
    assert validar_cuenta_exclusiva(
        "whatsapp", whatsapp_phone_number_id="123456789",
    ) is True


def test_vinculo_whatsapp_es_exclusivo():
    with pytest.raises(ValueError, match="otros canales"):
        validar_cuenta_exclusiva(
            "whatsapp", whatsapp_phone_number_id="123", mercado_libre_cuenta=object(),
        )


def test_registro_nace_desactivado_y_sin_credenciales():
    fuente = Path("services/estructura_admin.py").read_text(encoding="utf-8-sig")
    modelo = Path("models/vinculo_canal_comercial.py").read_text(encoding="utf-8-sig")
    assert 'estado="desactivado"' in fuente
    assert "whatsapp_phone_number_id" in modelo
    assert "token" not in modelo.lower()
    assert "secret" not in modelo.lower()


def test_contexto_acepta_vinculo_del_registro():
    payload = {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": "123"}
    }}]}]}
    contexto = resolver_contexto_webhook_whatsapp(payload, [{
        "whatsapp_phone_number_id": "123", "organizacion_id": 4,
        "unidad_negocio_id": 8, "estado": "activo",
    }])
    assert contexto["organizacion_id"] == 4


def test_webhook_productivo_no_fue_modificado_por_lote():
    fuente = Path("modules/whatsapp/webhook.py").read_text(encoding="utf-8-sig")
    assert "resolver_contexto_webhook_whatsapp" not in fuente
