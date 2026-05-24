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