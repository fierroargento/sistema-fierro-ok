from pathlib import Path


def test_limpieza_resuelve_contexto_por_pedido():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    servicio = Path(
        "services/ml_importacion.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def ml_api_contexto_de_pedido("
    )
    fin = app.index(
        "\ndef ml_sync_manual(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "cuenta_por_pedido_o_backfill_unica("
        in bloque
    )
    assert "ml_api_contexto(" in bloque
    assert "api_context.get" in bloque
    assert "api_context=api_context" in bloque
    assert (
        "ml_obtener_order_de_pedido,"
        in bloque
    )
    assert (
        "ml_obtener_shipment_de_pedido,"
        in bloque
    )

    inicio_servicio = servicio.index(
        "def "
        "ml_limpiar_pedidos_ml_no_operables_"
        "existentes_service("
    )
    fin_servicio = servicio.index(
        "\ndef ml_procesar_orders_sync_service(",
        inicio_servicio,
    )
    bloque_servicio = servicio[
        inicio_servicio:fin_servicio
    ]

    compacto_servicio = "".join(
        bloque_servicio.split()
    )

    assert (
        "ml_obtener_order(pedido,order_id,)"
        in compacto_servicio
    )
    assert (
        "ml_obtener_shipment(pedido,"
        in compacto_servicio
    )


def test_limpieza_no_usa_api_global_en_app():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def ml_limpiar_pedidos_ml_no_operables_existentes("
    )
    fin = app.index(
        "\ndef ml_sync_manual(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "ml_obtener_order," not in bloque
    assert "ml_obtener_shipment," not in bloque


def test_limpieza_aisla_error_de_un_pedido():
    servicio = Path(
        "services/ml_importacion.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    inicio = servicio.index(
        "def "
        "ml_limpiar_pedidos_ml_no_operables_"
        "existentes_service("
    )
    fin = servicio.index(
        "\ndef ml_procesar_orders_sync_service(",
        inicio,
    )
    bloque = servicio[inicio:fin]
    compacto = "".join(bloque.split())

    assert "exceptExceptionaserror:" in compacto
    assert "nosepudoverificar" in compacto
    assert "consucuentaML" in compacto
    assert (
        "detalles.append("
        in bloque
    )
    assert "continue" in bloque
