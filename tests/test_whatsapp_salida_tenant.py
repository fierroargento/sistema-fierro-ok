import pytest

from services.whatsapp_salida_tenant import (
    ConfiguracionSalidaWhatsAppError,
    certificar_configuraciones_salida_whatsapp,
    nombres_variables_credencial,
    resolver_configuracion_salida_whatsapp,
)


def vinculo(org, unidad, phone, estado="activo"):
    return {
        "canal": "whatsapp", "organizacion_id": org,
        "unidad_negocio_id": unidad, "whatsapp_phone_number_id": phone,
        "estado": estado,
    }


def test_fierro_y_nautica_resuelven_secretos_separados():
    fierro = vinculo(1, 10, "PHONE-FIERRO")
    nautica = vinculo(2, 20, "PHONE-NAUTICA")
    variables_f = nombres_variables_credencial("PHONE-FIERRO")
    variables_n = nombres_variables_credencial("PHONE-NAUTICA")
    entorno = {variables_f["token"]: "secreto-f", variables_n["token"]: "secreto-n"}
    config_f = resolver_configuracion_salida_whatsapp(
        [fierro, nautica], organizacion_id=1, unidad_negocio_id=10, environ=entorno
    )
    config_n = resolver_configuracion_salida_whatsapp(
        [fierro, nautica], organizacion_id=2, unidad_negocio_id=20, environ=entorno
    )
    assert config_f.token == "secreto-f" and config_n.token == "secreto-n"
    assert config_f.api_url != config_n.api_url
    assert "secreto-f" not in repr(config_f)


def test_falta_o_ambiguedad_bloquean_sin_fallback_global():
    enlace = vinculo(1, 10, "PHONE-FIERRO")
    with pytest.raises(ConfiguracionSalidaWhatsAppError, match="falta WHATSAPP_TOKEN"):
        resolver_configuracion_salida_whatsapp(
            [enlace], organizacion_id=1, unidad_negocio_id=10,
            environ={"WHATSAPP_TOKEN": "global-prohibido"},
        )
    with pytest.raises(ConfiguracionSalidaWhatsAppError, match="ambiguo"):
        resolver_configuracion_salida_whatsapp(
            [enlace, dict(enlace)], organizacion_id=1, unidad_negocio_id=10,
            environ={},
        )


def test_certificacion_no_expone_secretos_ni_habilita_envios():
    enlace = vinculo(1, 10, "PHONE-FIERRO")
    variable = nombres_variables_credencial("PHONE-FIERRO")["token"]
    resultado = certificar_configuraciones_salida_whatsapp(
        [enlace], environ={variable: "secreto-ultra-reservado"}
    )
    assert resultado["preparadas"] == 1 and resultado["bloqueadas"] == 0
    assert resultado["autorizacion_activacion"] is False
    assert not any(resultado["controles"].values())
    assert "secreto-ultra-reservado" not in repr(resultado)
