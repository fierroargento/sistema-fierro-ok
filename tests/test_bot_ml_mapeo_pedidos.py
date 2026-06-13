from modules.bot_ml.mapeo_pedidos import (
    ml_mapear_tipo,
    ml_mapear_tipo_entrega,
    ml_nombre_cliente,
)


def test_ml_nombre_cliente_prefiere_receiver_address():
    order = {
        "buyer": {
            "first_name": "Juan",
            "last_name": "Perez",
            "nickname": "JUAN123",
        }
    }
    shipment = {
        "receiver_address": {
            "receiver_name": "Maria Gomez",
        }
    }

    assert ml_nombre_cliente(order, shipment) == "Maria Gomez"


def test_ml_nombre_cliente_usa_nombre_buyer_si_no_hay_receiver():
    order = {
        "buyer": {
            "first_name": "Juan",
            "last_name": "Perez",
            "nickname": "JUAN123",
        }
    }

    assert ml_nombre_cliente(order, {}) == "Juan Perez"


def test_ml_nombre_cliente_fallback_nickname():
    order = {
        "buyer": {
            "nickname": "JUAN123",
        }
    }

    assert ml_nombre_cliente(order, {}) == "JUAN123"


def test_ml_nombre_cliente_fallback_generico():
    assert ml_nombre_cliente({}, {}) == "Cliente Mercado Libre"


def test_ml_mapear_tipo_custom_es_acordas():
    order = {
        "shipping": {
            "mode": "custom",
        }
    }

    assert ml_mapear_tipo(order, {}) == "Acordás la Entrega"


def test_ml_mapear_tipo_me2_es_mercado_envios():
    order = {
        "shipping": {
            "mode": "me2",
        }
    }

    assert ml_mapear_tipo(order, {}) == "Mercado Envíos"


def test_ml_mapear_tipo_logistic_type_fulfillment_es_mercado_envios():
    shipment = {
        "logistic_type": "fulfillment",
    }

    assert ml_mapear_tipo({}, shipment) == "Mercado Envíos"


def test_ml_mapear_tipo_con_shipping_id_es_mercado_envios():
    order = {
        "shipping": {
            "id": "123",
        }
    }

    assert ml_mapear_tipo(order, {}) == "Mercado Envíos"


def test_ml_mapear_tipo_sin_shipping_es_acordas():
    assert ml_mapear_tipo({}, {}) == "Acordás la Entrega"


def test_ml_mapear_tipo_entrega_pickup_es_sucursal():
    shipment = {
        "shipping_option": {
            "delivery_type": "pickup",
        }
    }

    assert ml_mapear_tipo_entrega({}, shipment) == "Sucursal"


def test_ml_mapear_tipo_entrega_address_line_es_domicilio():
    shipment = {
        "receiver_address": {
            "address_line": "San Martin 123",
        }
    }

    assert ml_mapear_tipo_entrega({}, shipment) == "Domicilio"


def test_ml_mapear_tipo_entrega_sin_datos_es_vacio():
    assert ml_mapear_tipo_entrega({}, {}) == ""