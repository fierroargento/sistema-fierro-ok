from types import SimpleNamespace

from services.ml_shipment_webhook import ml_actualizar_pedido_con_shipment_webhook


def test_ml_actualizar_pedido_con_shipment_no_finaliza_si_ready_to_ship():
    pedido = SimpleNamespace(
        ml_shipping_id="",
        ml_shipping_status="",
        ml_logistic_type="",
        ml_shipping_mode="",
        seguimiento="",
        ultima_sync_ml=None,
        ml_tipo="Mercado Envíos",
        estado="Etiqueta Lista",
        fecha_entregado=None,
        observaciones="",
    )

    finalizado = ml_actualizar_pedido_con_shipment_webhook(
        pedido,
        {
            "id": 47397663321,
            "status": "ready_to_ship",
            "substatus": "printed",
            "mode": "me2",
            "logistic_type": "drop_off",
            "tracking_number": "HC465434421AR",
        },
        "47397663321",
    )

    assert finalizado is False
    assert pedido.estado == "Etiqueta Lista"
    assert pedido.fecha_entregado is None
    assert pedido.ml_shipping_id == "47397663321"
    assert pedido.ml_shipping_status == "ready_to_ship"
    assert pedido.ml_logistic_type == "drop_off"
    assert pedido.ml_shipping_mode == "me2"
    assert pedido.seguimiento == "HC465434421AR"


def test_ml_actualizar_pedido_con_shipment_finaliza_si_delivered():
    pedido = SimpleNamespace(
        ml_shipping_id="47397663321",
        ml_shipping_status="ready_to_ship",
        ml_logistic_type="drop_off",
        ml_shipping_mode="me2",
        seguimiento="HC465434421AR",
        ultima_sync_ml=None,
        ml_tipo="Mercado Envíos",
        estado="Despachado",
        fecha_entregado=None,
        observaciones="",
    )

    finalizado = ml_actualizar_pedido_con_shipment_webhook(
        pedido,
        {
            "id": 47397663321,
            "status": "delivered",
            "mode": "me2",
            "logistic_type": "drop_off",
            "tracking_number": "HC465434421AR",
        },
        "47397663321",
    )

    assert finalizado is True
    assert pedido.estado == "Finalizado"
    assert pedido.fecha_entregado is not None
    assert "ML Mercado Envíos informa entregado" in pedido.observaciones
