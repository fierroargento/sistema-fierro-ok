from services.telefonos import normalizar_telefono_service


def test_normaliza_numero_simple():
    assert normalizar_telefono_service("2920123456") == "5492920123456"


def test_normaliza_numero_con_mas():
    assert normalizar_telefono_service("+5492920123456") == "5492920123456"


def test_normaliza_numero_con_54():
    assert normalizar_telefono_service("542920123456") == "5492920123456"


def test_normaliza_numero_con_15():
    assert normalizar_telefono_service("152920123456") == "5492920123456"


def test_normaliza_numero_con_guiones():
    assert normalizar_telefono_service("2920-123456") == "5492920123456"


def test_normaliza_numero_con_espacios():
    assert normalizar_telefono_service("2920 123456") == "5492920123456"


def test_normaliza_none():
    assert normalizar_telefono_service(None) == ""


def test_normaliza_vacio():
    assert normalizar_telefono_service("") == ""


def test_normaliza_argentina_sin_cero_despues_de_549():
    from services.telefonos import normalizar_telefono_service

    assert normalizar_telefono_service("54901157347193") == "5491157347193"
    assert normalizar_telefono_service("+54 9 011 5734-7193") == "5491157347193"
    assert normalizar_telefono_service("01157347193") == "5491157347193"


def test_normaliza_argentina_quita_15_movil_con_codigo_area():
    from services.telefonos import normalizar_telefono_service

    assert normalizar_telefono_service("011 15 5734-7193") == "5491157347193"
    assert normalizar_telefono_service("+54 9 011 15 5734-7193") == "5491157347193"


def test_normaliza_argentina_no_toca_numero_correcto():
    from services.telefonos import normalizar_telefono_service

    assert normalizar_telefono_service("5491157347193") == "5491157347193"


def test_valida_telefono_whatsapp_argentina_correcto():
    from services.telefonos import (
        es_telefono_whatsapp_argentina_valido_service,
    )

    assert es_telefono_whatsapp_argentina_valido_service(
        "5491157347193"
    ) is True


def test_valida_telefono_whatsapp_argentina_despues_de_normalizar():
    from services.telefonos import (
        es_telefono_whatsapp_argentina_valido_service,
    )

    assert es_telefono_whatsapp_argentina_valido_service(
        "011 15 5734-7193"
    ) is True


def test_rechaza_telefono_whatsapp_argentina_corto():
    from services.telefonos import (
        es_telefono_whatsapp_argentina_valido_service,
    )

    assert es_telefono_whatsapp_argentina_valido_service(
        "549115734719"
    ) is False


def test_rechaza_telefono_whatsapp_argentina_vacio():
    from services.telefonos import (
        es_telefono_whatsapp_argentina_valido_service,
    )

    assert es_telefono_whatsapp_argentina_valido_service("") is False
