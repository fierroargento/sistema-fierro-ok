from types import SimpleNamespace

from services.ml_estados import (
    ml_estado_order_service,
    ml_estado_shipment_service,
    ml_logistica_no_operable_service,
    ml_es_envio_full_service,
)


def test_ml_estado_order_normaliza():
    order = {
        "status": " PAID "
    }

    assert (
        ml_estado_order_service(order)
        == "paid"
    )


def test_ml_estado_shipment_prioriza_shipment():
    order = {
        "shipping": {
            "status": "pending"
        }
    }

    shipment = {
        "status": "shipped"
    }

    assert (
        ml_estado_shipment_service(
            order,
            shipment,
        )
        == "shipped"
    )


def test_ml_detecta_full():
    order = {
        "tags": ["meli_full"]
    }

    shipment = {}

    no_operable, motivo = (
        ml_logistica_no_operable_service(
            order,
            shipment,
        )
    )

    assert no_operable is True
    assert motivo == "Mercado Envíos Full"


def test_ml_detecta_flex():
    order = {
        "shipping": {
            "logistic_type": "self_service"
        }
    }

    shipment = {}

    no_operable, motivo = (
        ml_logistica_no_operable_service(
            order,
            shipment,
        )
    )

    assert no_operable is True
    assert motivo == "Mercado Envíos Flex"


def test_ml_es_envio_full():
    order = {
        "tags": ["full"]
    }

    shipment = {}

    assert (
        ml_es_envio_full_service(
            order,
            shipment,
            ml_logistica_no_operable_service,
        )
        is True
    )

from services.ml_estados import (
    ml_order_esta_entregado_service,
    ml_order_debe_omitirse_service,
)


def test_ml_entregado_por_shipment_delivered():
    order = {
        "id": "1001",
        "status": "paid",
        "shipping": {
            "logistic_type": "drop_off",
        },
    }

    shipment = {
        "status": "delivered",
    }

    assert (
        ml_order_esta_entregado_service(
            order,
            shipment,
            ml_estado_order_service,
            ml_estado_shipment_service,
        )
        is True
    )


def test_ml_acordas_closed_no_es_entregado():
    order = {
        "id": "1002",
        "status": "closed",
        "shipping": {
            "logistic_type": "",
        },
        "tags": [],
    }

    shipment = {}

    assert (
        ml_order_esta_entregado_service(
            order,
            shipment,
            ml_estado_order_service,
            ml_estado_shipment_service,
        )
        is False
    )


def test_ml_mercado_envios_closed_sin_cancelacion_es_entregado():
    order = {
        "id": "1003",
        "status": "closed",
        "shipping": {
            "logistic_type": "drop_off",
        },
        "tags": [],
    }

    shipment = {}

    assert (
        ml_order_esta_entregado_service(
            order,
            shipment,
            ml_estado_order_service,
            ml_estado_shipment_service,
        )
        is True
    )


def test_ml_mercado_envios_closed_cancelado_no_es_entregado():
    order = {
        "id": "1004",
        "status": "closed",
        "shipping": {
            "logistic_type": "drop_off",
        },
        "tags": ["cancelled"],
    }

    shipment = {}

    assert (
        ml_order_esta_entregado_service(
            order,
            shipment,
            ml_estado_order_service,
            ml_estado_shipment_service,
        )
        is False
    )


def test_ml_order_debe_omitirse_si_entregado():
    order = {
        "id": "1005",
        "status": "paid",
        "shipping": {
            "logistic_type": "drop_off",
        },
    }

    shipment = {
        "status": "delivered",
    }

    debe_omitirse, motivo = ml_order_debe_omitirse_service(
        order,
        shipment,
        ml_pedido_esta_ignorado=lambda order_id: False,
        ml_order_esta_entregado=lambda order, shipment: ml_order_esta_entregado_service(
            order,
            shipment,
            ml_estado_order_service,
            ml_estado_shipment_service,
        ),
        ml_estado_order=ml_estado_order_service,
        ml_logistica_no_operable=ml_logistica_no_operable_service,
    )

    assert debe_omitirse is True
    assert "entregado" in motivo.lower()

from services.ml_estados import (
    ml_envio_ya_despachado_service,
)


def test_ml_envio_despachado_por_shipped():
    order = {
        "shipping": {
            "status": "shipped"
        }
    }

    assert (
        ml_envio_ya_despachado_service(order)
        is True
    )


def test_ml_envio_despachado_por_delivered():
    order = {
        "shipping": {
            "status": "delivered"
        }
    }

    assert (
        ml_envio_ya_despachado_service(order)
        is True
    )


def test_ml_envio_despachado_por_returned():
    order = {
        "shipping": {
            "status": "returned"
        }
    }

    assert (
        ml_envio_ya_despachado_service(order)
        is True
    )


def test_ml_envio_no_despachado_pending():
    order = {
        "shipping": {
            "status": "pending"
        }
    }

    assert (
        ml_envio_ya_despachado_service(order)
        is False
    )


def test_ml_envio_despachado_prioriza_shipment():
    order = {
        "shipping": {
            "status": "pending"
        }
    }

    shipment = {
        "status": "shipped"
    }

    assert (
        ml_envio_ya_despachado_service(
            order,
            shipment,
        )
        is True
    )

from domain.estados import Estado

from services.ml_estados import (
    ml_marcar_pedido_finalizado_por_entrega_service,
    ml_borrar_pedido_importado_si_corresponde_service,
)


def test_ml_marcar_pedido_finalizado_por_entrega():
    pedido = SimpleNamespace(
        origen="",
        canal="",
        id_venta="",
        ml_order_status="",
        ml_shipping_status="",
        estado=Estado.CARGANDO,
        fecha_entregado=None,
        ultima_sync_ml=None,
        observaciones="",
    )

    order = {
        "id": "2001",
        "status": "paid",
    }

    shipment = {
        "status": "delivered",
    }

    resultado = ml_marcar_pedido_finalizado_por_entrega_service(
        pedido,
        order,
        shipment,
        ml_estado_order_service,
        ml_estado_shipment_service,
    )

    assert resultado is pedido
    assert pedido.origen == "mercadolibre"
    assert pedido.canal == "Mercado Libre"
    assert pedido.id_venta == "2001"
    assert pedido.ml_order_status == "paid"
    assert pedido.ml_shipping_status == "delivered"
    assert pedido.estado == Estado.FINALIZADO
    assert pedido.fecha_entregado is not None
    assert pedido.ultima_sync_ml is not None
    assert "ML informa venta entregada" in pedido.observaciones


def test_ml_borrar_pedido_importado_finaliza_sin_borrar():
    pedido = SimpleNamespace(
        canal="Mercado Libre",
        origen="mercadolibre",
        estado=Estado.CARGANDO,
        observaciones="",
    )

    resultado = ml_borrar_pedido_importado_si_corresponde_service(
        pedido,
        Estado,
    )

    assert resultado is True
    assert pedido.estado == Estado.FINALIZADO
    assert "No se borró para preservar auditoría" in pedido.observaciones


def test_ml_borrar_pedido_importado_no_toca_si_no_es_ml():
    pedido = SimpleNamespace(
        canal="Tienda Nube",
        origen="tiendanube",
        estado=Estado.CARGANDO,
        observaciones="",
    )

    resultado = ml_borrar_pedido_importado_si_corresponde_service(
        pedido,
        Estado,
    )

    assert resultado is False
    assert pedido.estado == Estado.CARGANDO            