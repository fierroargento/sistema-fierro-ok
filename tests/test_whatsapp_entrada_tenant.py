import inspect

import pytest

from services.whatsapp_entrada_tenant import (
    ConfiguracionEntradaWhatsAppError,
    nombres_variables_entrada,
    resolver_configuracion_post_whatsapp,
    resolver_configuracion_verificacion_whatsapp,
)


def vinculo(org, unidad, phone, estado="activo"):
    return {
        "canal": "whatsapp",
        "organizacion_id": org,
        "unidad_negocio_id": unidad,
        "whatsapp_phone_number_id": phone,
        "estado": estado,
    }


def payload(phone):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone},
    }}]}]}


def test_post_resuelve_app_secret_exclusivo_sin_exponerlo():
    fierro = vinculo(1, 10, "PHONE-FIERRO")
    nautica = vinculo(2, 20, "PHONE-NAUTICA")
    variable_f = nombres_variables_entrada("PHONE-FIERRO")["app_secret"]
    variable_n = nombres_variables_entrada("PHONE-NAUTICA")["app_secret"]

    config = resolver_configuracion_post_whatsapp(
        payload("PHONE-NAUTICA"), [fierro, nautica],
        environ={variable_f: "secret-fierro", variable_n: "secret-nautica"},
    )

    assert (config.organizacion_id, config.unidad_negocio_id) == (2, 20)
    assert config.app_secret == "secret-nautica"
    assert "secret-nautica" not in repr(config)


def test_post_sin_secret_especifico_bloquea_y_no_usa_global():
    enlace = vinculo(1, 10, "PHONE-FIERRO")

    with pytest.raises(ConfiguracionEntradaWhatsAppError, match="falta WHATSAPP_APP_SECRET"):
        resolver_configuracion_post_whatsapp(
            payload("PHONE-FIERRO"), [enlace],
            environ={"WHATSAPP_APP_SECRET": "global-prohibido"},
        )


def test_get_resuelve_token_de_verificacion_y_tenant_correctos():
    fierro = vinculo(1, 10, "PHONE-FIERRO")
    nautica = vinculo(2, 20, "PHONE-NAUTICA")
    variable_f = nombres_variables_entrada("PHONE-FIERRO")["verify_token"]
    variable_n = nombres_variables_entrada("PHONE-NAUTICA")["verify_token"]

    config = resolver_configuracion_verificacion_whatsapp(
        "verify-nautica", [fierro, nautica],
        environ={variable_f: "verify-fierro", variable_n: "verify-nautica"},
    )

    assert (config.organizacion_id, config.unidad_negocio_id) == (2, 20)
    assert config.phone_number_id == "PHONE-NAUTICA"
    assert "verify-nautica" not in repr(config)


def test_get_rechaza_token_global_y_token_duplicado():
    fierro = vinculo(1, 10, "PHONE-FIERRO")
    nautica = vinculo(2, 20, "PHONE-NAUTICA")
    variable_f = nombres_variables_entrada("PHONE-FIERRO")["verify_token"]
    variable_n = nombres_variables_entrada("PHONE-NAUTICA")["verify_token"]

    with pytest.raises(ConfiguracionEntradaWhatsAppError, match="sin cuenta"):
        resolver_configuracion_verificacion_whatsapp(
            "global", [fierro, nautica],
            environ={"WHATSAPP_VERIFY_TOKEN": "global"},
        )
    with pytest.raises(ConfiguracionEntradaWhatsAppError, match="ambigua"):
        resolver_configuracion_verificacion_whatsapp(
            "repetido", [fierro, nautica],
            environ={variable_f: "repetido", variable_n: "repetido"},
        )


def test_variables_de_entrada_son_distintas_por_phone_number_id():
    assert nombres_variables_entrada("PHONE-FIERRO") != nombres_variables_entrada(
        "PHONE-NAUTICA"
    )


def test_resolucion_pura_no_realiza_transporte_ni_persistencia():
    import services.whatsapp_entrada_tenant as modulo

    fuente = inspect.getsource(modulo)
    for prohibido in ("requests", "urlopen", "db.session", "commit(", "os.environ"):
        assert prohibido not in fuente
