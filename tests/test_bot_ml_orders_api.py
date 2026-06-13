import pytest

from modules.bot_ml.orders_api import (
    ml_obtener_order_api,
    ml_obtener_orders_recientes_api,
    ml_obtener_shipment_api,
    ml_obtener_usuario_actual_api,
)


class CuentaFake:
    def __init__(self, user_id_ml="12345"):
        self.user_id_ml = user_id_ml


def test_ml_obtener_usuario_actual_api_delega_en_api_get():
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))
        return {"id": "seller-1"}

    resultado = ml_obtener_usuario_actual_api(fake_api_get)

    assert resultado == {"id": "seller-1"}
    assert llamadas == [("/users/me", None)]


def test_ml_obtener_orders_recientes_api_requiere_user_id():
    cuenta = CuentaFake(user_id_ml="")

    with pytest.raises(ValueError) as exc:
        ml_obtener_orders_recientes_api(cuenta, lambda path, params=None: {})

    assert "user_id" in str(exc.value)


def test_ml_obtener_orders_recientes_api_pagina_resultados():
    cuenta = CuentaFake(user_id_ml="seller-1")
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))

        if params["offset"] == 0:
            return {
                "results": [{"id": "orden-1"}],
                "paging": {"total": 51},
            }

        return {
            "results": [{"id": "orden-2"}],
            "paging": {"total": 51},
        }

    resultado = ml_obtener_orders_recientes_api(
        cuenta,
        fake_api_get,
        horas=24,
        max_paginas=5,
    )

    assert resultado == [{"id": "orden-1"}, {"id": "orden-2"}]
    assert llamadas[0][0] == "/orders/search"
    assert llamadas[0][1]["seller"] == "seller-1"
    assert llamadas[0][1]["limit"] == 50
    assert llamadas[0][1]["offset"] == 0
    assert llamadas[1][1]["offset"] == 50


def test_ml_obtener_orders_recientes_api_corta_si_no_hay_resultados():
    cuenta = CuentaFake(user_id_ml="seller-1")
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))
        return {
            "results": [],
            "paging": {"total": 0},
        }

    resultado = ml_obtener_orders_recientes_api(
        cuenta,
        fake_api_get,
        horas=24,
        max_paginas=5,
    )

    assert resultado == []
    assert len(llamadas) == 1


def test_ml_obtener_order_api_devuelve_vacio_sin_order_id():
    assert ml_obtener_order_api("", lambda path, params=None: {"id": "x"}) == {}


def test_ml_obtener_order_api_consulta_order():
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))
        return {"id": "200"}

    resultado = ml_obtener_order_api("200", fake_api_get)

    assert resultado == {"id": "200"}
    assert llamadas == [("/orders/200", None)]


def test_ml_obtener_order_api_captura_error():
    def fake_api_get(path, params=None):
        raise ValueError("fallo")

    assert ml_obtener_order_api("200", fake_api_get) == {}


def test_ml_obtener_shipment_api_devuelve_vacio_sin_shipping_id():
    assert ml_obtener_shipment_api("", lambda path, params=None: {"id": "x"}) == {}


def test_ml_obtener_shipment_api_consulta_shipment():
    llamadas = []

    def fake_api_get(path, params=None):
        llamadas.append((path, params))
        return {"id": "300"}

    resultado = ml_obtener_shipment_api("300", fake_api_get)

    assert resultado == {"id": "300"}
    assert llamadas == [("/shipments/300", None)]


def test_ml_obtener_shipment_api_captura_error():
    def fake_api_get(path, params=None):
        raise ValueError("fallo")

    assert ml_obtener_shipment_api("300", fake_api_get) == {}