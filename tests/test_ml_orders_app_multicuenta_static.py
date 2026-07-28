from pathlib import Path


def test_orders_recientes_usa_contexto_de_cuenta_recibida():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def ml_obtener_orders_recientes("
    )
    fin = app.index(
        "\ndef ml_obtener_order(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "ml_api_contexto(" in bloque
    assert "cuenta," in bloque
    assert "api_context.get_json" in bloque
    assert "\n        ml_api_get," not in bloque
