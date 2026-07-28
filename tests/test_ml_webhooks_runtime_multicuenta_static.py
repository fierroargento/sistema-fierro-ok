from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def _bloque(firma):
    app = _app()
    inicio = app.index(firma)
    fin = app.find("\ndef ", inicio + len(firma))

    if fin == -1:
        fin = len(app)

    return app[inicio:fin]


def test_webhook_propaga_user_id_a_todos_los_flujos():
    bloque = _bloque("def webhook_mercadolibre(")

    assert 'data.get("user_id")' in bloque

    for llamada in (
        "ml_sync_pedido_por_order_id_webhook(",
        "ml_sync_shipment_por_id_webhook(",
        "ml_marcar_reclamo_webhook(",
    ):
        assert llamada in bloque

    assert bloque.count(
        "seller_id=seller_id_webhook"
    ) == 3


def test_contexto_webhook_no_adivina_entre_dos_cuentas():
    bloque = _bloque("def ml_api_contexto_webhook(")

    assert "cuenta_por_seller_id(" in bloque
    assert "cuentas_activas(" in bloque
    assert "if len(cuentas) != 1:" in bloque
    assert "ml_api_contexto(" in bloque


def test_order_shipment_y_claim_usan_contexto_webhook():
    order = _bloque(
        "def ml_sync_pedido_por_order_id_webhook("
    )
    shipment = _bloque(
        "def ml_sync_shipment_por_id_webhook("
    )
    claim = _bloque(
        "def ml_marcar_reclamo_webhook("
    )

    assert "api_context.get" in order
    assert "cuenta_ml=api_context.cuenta" in order

    assert "api_context=api_context" in shipment
    assert "seller_id=seller_id" in shipment

    assert "api_context.get(" in claim
    assert "ml_api_get(" not in claim


def test_validacion_despacho_liga_consultas_al_pedido():
    bloque = _bloque(
        "def ml_validar_orden_operable_antes_de_despacho("
    )

    assert "ml_obtener_order_de_pedido(" in bloque
    assert "ml_obtener_shipment_de_pedido(" in bloque
    assert "ml_obtener_claim_de_pedido(" in bloque

    assert "\n        ml_obtener_order," not in bloque
    assert "\n        ml_obtener_shipment," not in bloque
    assert (
        "\n        ml_obtener_claim_de_order,"
        not in bloque
    )


def test_chat_y_detalle_no_consultan_con_cuenta_global():
    chat = _bloque(
        "def ml_obtener_ids_chat_pedido("
    )
    app = _app()

    assert "ml_obtener_order_de_pedido(" in chat
    assert "ml_api_get(" not in chat

    assert (
        "claim_live = ml_obtener_claim_de_pedido("
        in app
    )
    assert (
        "claim_live = ml_obtener_claim_de_order("
        not in app
    )
