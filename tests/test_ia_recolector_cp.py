from pathlib import Path

from services.ia_recolector_datos import (
    ia_extraer_codigo_postal_simple_service,
    resolver_codigo_postal_contextual,
)


def test_extrae_cp_como_unico_mensaje():
    assert (
        ia_extraer_codigo_postal_simple_service(
            "3500"
        )
        == "3500"
    )


def test_extrae_cp_con_prefijos_admitidos():
    casos = {
        "CP 3500": "3500",
        "C.P. 8504": "8504",
        "Código postal: 1612": "1612",
        "cod postal-1888": "1888",
    }

    for texto, esperado in casos.items():
        assert (
            ia_extraer_codigo_postal_simple_service(
                texto
            )
            == esperado
        )


def test_no_extrae_numero_sin_contexto_de_cp():
    assert (
        ia_extraer_codigo_postal_simple_service(
            "Mi pedido es el número 3500"
        )
        == ""
    )


def test_contextual_acepta_cuatro_digitos_si_falta_cp():
    assert resolver_codigo_postal_contextual(
        "El dato es 8504",
        faltantes_actuales=["codigo_postal"],
    ) == "8504"


def test_contextual_usa_faltantes_guardados():
    assert resolver_codigo_postal_contextual(
        "8504",
        faltantes_actuales=[],
        faltantes_guardados='["codigo postal"]',
    ) == "8504"


def test_contextual_permite_corregir_cp_existente():
    assert resolver_codigo_postal_contextual(
        "8504",
        faltantes_actuales=[],
        codigo_postal_actual="8500",
    ) == "8504"


def test_contextual_conserva_prefijo_explicito():
    assert resolver_codigo_postal_contextual(
        "Mi CP: 2761",
        faltantes_actuales=[],
        codigo_postal_actual="",
    ) == "2761"


def test_contextual_sin_cp_devuelve_vacio():
    assert resolver_codigo_postal_contextual(
        "Hola, quería consultar por el envío",
        faltantes_actuales=["codigo_postal"],
    ) == ""


def test_app_conserva_wrapper_y_delega_regla_contextual():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio_wrapper = app.index(
        "def ia_extraer_codigo_postal_simple("
    )
    fin_wrapper = app.index(
        "\ndef ",
        inicio_wrapper + 1,
    )
    wrapper = app[inicio_wrapper:fin_wrapper]

    inicio_analizador = app.index(
        "def ia_analizar_ultimo_mensaje_pedido("
    )
    fin_analizador = app.index(
        "\ndef ia_auto_responder_post_analisis(",
        inicio_analizador,
    )
    analizador = app[
        inicio_analizador:fin_analizador
    ]

    assert (
        "ia_extraer_codigo_postal_simple_service("
        in wrapper
    )
    assert (
        "resolver_codigo_postal_contextual("
        in analizador
    )
    assert "posible_cp_contextual" not in analizador
    assert "texto_limpio_cp" not in analizador
