from services.whatsapp_template_params import (
    sanitizar_parametro_template_meta,
    sanitizar_parametros_template_meta,
)


def test_sanitizar_parametro_template_meta_quita_saltos_de_linea():
    texto = sanitizar_parametro_template_meta(". localidad\n. código postal")

    assert texto == ". localidad . código postal"
    assert "\n" not in texto


def test_sanitizar_parametro_template_meta_quita_tabs_y_espacios_largos():
    texto = sanitizar_parametro_template_meta("DNI\t\t    código postal")

    assert texto == "DNI código postal"
    assert "\t" not in texto
    assert "     " not in texto


def test_sanitizar_parametros_template_meta_lista():
    parametros = sanitizar_parametros_template_meta([
        "Débora",
        ". localidad\n. código postal",
    ])

    assert parametros == [
        "Débora",
        ". localidad . código postal",
    ]
