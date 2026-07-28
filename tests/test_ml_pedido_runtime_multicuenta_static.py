from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def _bloque(app, inicio_texto, fin_texto):
    inicio = app.index(inicio_texto)
    fin = app.index(fin_texto, inicio)
    return app[inicio:fin]


def test_sync_mensajes_no_elige_cuenta_global():
    app = _app()
    bloque = _bloque(
        app,
        "def ml_sync_mensajes_pendientes_pedidos(",
        "\ndef ml_pedido_tiene_mensajes_pendientes(",
    )

    assert "cuenta_ml_actual()" not in bloque
    assert "ml_sync_mensajes_pedido(pedido)" in bloque


def test_resync_manual_usa_contexto_del_pedido():
    app = _app()
    bloque = _bloque(
        app,
        "def resync_ml_pedido(",
        "\n\n@app.route("
        "\"/pedido/<int:id>/sync-mensajes-ml\"",
    )

    assert "ml_api_contexto_de_pedido(" in bloque
    assert "ml_obtener_order_de_pedido(" in bloque
    assert "cuenta_ml=api_context.cuenta" in bloque
    assert "api_context=api_context" in bloque
    assert "ml_obtener_claim_de_pedido(" in bloque

    prohibidos = [
        "ml_obtener_order(order_id)",
        "ml_obtener_claim_de_order(",
        "cuenta_ml_actual()",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque


def test_tracking_cancelacion_usa_contexto_del_pedido():
    app = _app()
    bloque = _bloque(
        app,
        "def actualizar_tracking_externo_pedido(",
        "\n\ndef ",
    )

    assert "ml_obtener_order_de_pedido(" in bloque
    assert "ml_api_contexto_de_pedido(" in bloque
    assert "api_context.seller_id" in bloque
    assert "data_search = api_context.get(" in bloque
    assert "ml_obtener_claim_de_pedido(" in bloque

    prohibidos = [
        "ml_obtener_order(pedido.id_venta)",
        "cuenta_ml_actual()",
        "data_search = ml_api_get(",
        "ml_obtener_claim_de_order(",
    ]

    for prohibido in prohibidos:
        assert prohibido not in bloque
