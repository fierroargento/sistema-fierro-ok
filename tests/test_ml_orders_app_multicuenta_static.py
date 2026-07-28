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
    assert "api_context.get" in bloque
    assert "api_context.get_json" not in bloque
    assert "\n        ml_api_get," not in bloque


def test_upsert_asigna_identidad_de_cuenta_al_pedido():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def ml_upsert_pedido_desde_order("
    )
    fin = app.index(
        "\ndef ml_borrar_pedidos_ml_cargando_importados(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "cuenta_ml=None" in bloque
    assert (
        "ml_resolver_cuenta_desde_order_service("
        in bloque
    )
    assert "cuenta_ml=cuenta_resuelta" in bloque
    assert (
        bloque.index(
            "ml_resolver_cuenta_desde_order_service("
        )
        < bloque.index(
            "ml_obtener_shipment("
        )
    )
    assert (
        "ml_asignar_cuenta_ml_a_pedido_service("
        in bloque
    )
    assert "cuenta_ml=cuenta_ml" in bloque
    assert "if not cuenta_asignada:" in bloque
    assert (
        bloque.index(
            "ml_asignar_cuenta_ml_a_pedido_service("
        )
        < bloque.index(
            "ml_sincronizar_items_pedido_service("
        )
    )


def test_upsert_usa_contexto_de_cuenta_en_todas_las_consultas():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def ml_upsert_pedido_desde_order("
    )
    fin = app.index(
        "\ndef ml_borrar_pedidos_ml_cargando_importados(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "ml_api_contexto(" in bloque
    assert "cuenta_resuelta," in bloque
    assert "api_context=api_context" in bloque
    assert (
        bloque.count("api_context=api_context")
        == 3
    )
    assert "ml_obtener_shipment(" in bloque
    assert "ml_obtener_billing_info(" in bloque
    assert (
        "ml_preparar_etiqueta_mercado_envios("
        in bloque
    )
    assert "ml_api_get," not in bloque
    assert "ml_access_token_vigente()" not in bloque
