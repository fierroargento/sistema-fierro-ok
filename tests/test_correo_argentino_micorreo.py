import pytest

from services.correo_argentino_micorreo import (
    MicorreoConfig,
    consultar_sucursales,
    cotizar_envio,
    normalizar_sucursal,
    obtener_customer_id,
    obtener_token,
    validar_usuario_micorreo,
)


def cfg(**overrides):
    base = dict(
        enabled=True,
        base_url="https://api.test/micorreo/v1",
        integracion_user="int_user",
        integracion_pass="int_pass",
        micorreo_user="mi@correo.com",
        micorreo_pass="mi_pass",
        customer_id="",
        cp_origen="8500",
        timeout=5,
    )
    base.update(overrides)
    return MicorreoConfig(**base)


def test_obtener_token_ok(monkeypatch):
    llamadas = []

    def fake_request(method, path, config, token=None, body=None, query=None, basic_auth=None):
        llamadas.append((method, path, basic_auth))
        return 200, {"token": "TOKEN_TEST", "expire": "2026-06-18 20:00:00"}

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", fake_request)

    r = obtener_token(cfg())

    assert r["ok"] is True
    assert r["token"] == "TOKEN_TEST"
    assert llamadas == [("POST", "/token", ("int_user", "int_pass"))]


def test_obtener_customer_id_usa_env_si_esta_configurado(monkeypatch):
    def no_deberia_llamarse(*args, **kwargs):
        raise AssertionError("No debería llamar a la API si customer_id está configurado")

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", no_deberia_llamarse)

    r = obtener_customer_id(cfg(customer_id="1233931"))

    assert r["ok"] is True
    assert r["customer_id"] == "1233931"
    assert r["fuente"] == "env"


def test_validar_usuario_micorreo_ok(monkeypatch):
    def fake_request(method, path, config, token=None, body=None, query=None, basic_auth=None):
        assert method == "POST"
        assert path == "/users/validate"
        assert token == "TOKEN_TEST"
        assert body == {"email": "mi@correo.com", "password": "mi_pass"}
        return 200, {"customerId": "1233931"}

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", fake_request)

    r = validar_usuario_micorreo("TOKEN_TEST", cfg())

    assert r["ok"] is True
    assert r["customer_id"] == "1233931"


def test_normalizar_sucursal_micorreo():
    r = normalizar_sucursal({
        "code": "R0100",
        "name": "S. C. DE BARILOCHE",
        "location": {
            "street_name": "Mitre",
            "street_number": "100",
            "city_name": "Bariloche",
            "state_name": "Río Negro",
            "zip_code": "8400",
            "geolocation": {
                "latitude": "-41.13",
                "longitude": "-71.31",
            },
        },
        "schedule": "LUN A VIE 08.00 A 14.30",
    })

    assert r["codigo"] == "R0100"
    assert r["nombre"] == "S. C. DE BARILOCHE"
    assert r["direccion"] == "Mitre 100"
    assert r["localidad"] == "Bariloche"
    assert r["provincia"] == "Río Negro"
    assert r["cp"] == "8400"


def test_consultar_sucursales_ok(monkeypatch):
    monkeypatch.setattr(
        "services.correo_argentino_micorreo._obtener_token_y_customer_id",
        lambda config=None, token=None, customer_id=None: {
            "ok": True,
            "status": 200,
            "token": "TOKEN_TEST",
            "customer_id": "1233931",
        },
    )

    def fake_request(method, path, config, token=None, body=None, query=None, basic_auth=None):
        assert method == "GET"
        assert path == "/agencies"
        assert token == "TOKEN_TEST"
        assert query == {"customerId": "1233931", "provinceCode": "R"}
        return 200, [
            {
                "code": "R0100",
                "name": "S. C. DE BARILOCHE",
                "location": {"city_name": "Bariloche"},
            }
        ]

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", fake_request)

    r = consultar_sucursales(province_code="R", config=cfg())

    assert r["ok"] is True
    assert r["cantidad"] == 1
    assert r["sucursales"][0]["codigo"] == "R0100"


def test_cotizar_envio_ok_acepta_202(monkeypatch):
    monkeypatch.setattr(
        "services.correo_argentino_micorreo._obtener_token_y_customer_id",
        lambda config=None, token=None, customer_id=None: {
            "ok": True,
            "status": 200,
            "token": "TOKEN_TEST",
            "customer_id": "1233931",
        },
    )

    def fake_request(method, path, config, token=None, body=None, query=None, basic_auth=None):
        assert method == "POST"
        assert path == "/rates"
        assert token == "TOKEN_TEST"
        assert body["customerId"] == "1233931"
        assert body["postalCodeOrigin"] == "8500"
        assert body["postalCodeDestination"] == "1000"
        assert body["deliveredType"] == "D"
        assert body["dimensions"]["weight"] == 3200

        return 202, {
            "rates": [
                {
                    "productName": "Correo Argentino Clasico",
                    "price": 15957.0,
                    "deliveryTimeMin": 2,
                    "deliveryTimeMax": 5,
                }
            ]
        }

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", fake_request)

    r = cotizar_envio(
        cp_destino="1000",
        modalidad="domicilio",
        peso_gr=3200,
        alto_cm=5,
        ancho_cm=42,
        largo_cm=36,
        config=cfg(),
    )

    assert r["ok"] is True
    assert r["status"] == 202
    assert r["modalidad"] == "D"
    assert r["cotizaciones"][0]["producto"] == "Correo Argentino Clasico"
    assert r["cotizaciones"][0]["precio"] == 15957.0
from services.correo_argentino_micorreo import consultar_tracking_envio
from tests.test_correo_argentino_micorreo import cfg


def test_consultar_tracking_envio_ok(monkeypatch):
    def fake_request(method, path, config, token=None, body=None, query=None, basic_auth=None):
        assert method == "GET"
        assert path == "/shipping/tracking"
        assert token == "TOKEN_TEST"
        assert body == {"shippingId": "000500076393019A3G0C701"}
        return 200, [
            {
                "id": "000017496",
                "productId": "HC",
                "trackingNumber": "000500076393019A3G0C701",
                "events": [
                    {
                        "event": "PREIMPOSICION",
                        "date": "28-08-2024 10:33",
                        "branch": "CORREO ARGENTINO",
                        "status": "",
                        "sign": "",
                    }
                ],
            }
        ]

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", fake_request)

    r = consultar_tracking_envio(
        "000500076393019A3G0C701",
        config=cfg(),
        token="TOKEN_TEST",
    )

    assert r["ok"] is True
    assert r["estado"] == "PREIMPOSICION"
    assert r["tracking_number"] == "000500076393019A3G0C701"
    assert r["eventos"][0]["sucursal"] == "CORREO ARGENTINO"


def test_consultar_tracking_envio_error_200_con_error(monkeypatch):
    def fake_request(method, path, config, token=None, body=None, query=None, basic_auth=None):
        return 200, {
            "date": "2025-01-13T14:56:09.832-03:00",
            "error": "No existe el cliente o pedido",
            "code": "0",
        }

    monkeypatch.setattr("services.correo_argentino_micorreo._request_json", fake_request)

    r = consultar_tracking_envio("NO_EXISTE", config=cfg(), token="TOKEN_TEST")

    assert r["ok"] is False
    assert "no existe" in r["error"].lower()


def test_obtener_capacidades_apaga_todo_si_integracion_deshabilitada():
    from services.correo_argentino_micorreo import obtener_capacidades

    r = obtener_capacidades(cfg(enabled=False))

    assert r["enabled"] is False
    assert all(v is False for v in r["funciones"].values())


def test_obtener_capacidades_default_seguro():
    from services.correo_argentino_micorreo import obtener_capacidades

    r = obtener_capacidades(cfg(enabled=True))

    assert r["funciones"]["cotizacion"] is True
    assert r["funciones"]["sucursales"] is True
    assert r["funciones"]["tracking"] is True
    assert r["funciones"]["importacion_envios"] is False
    assert r["funciones"]["etiquetas"] is False
    assert r["funciones"]["pago"] is False


def test_cotizar_envio_no_llama_api_si_funcion_deshabilitada(monkeypatch):
    from services.correo_argentino_micorreo import cotizar_envio

    monkeypatch.setenv("CORREO_MICORREO_FEATURE_COTIZACION", "false")

    def explotar(*args, **kwargs):
        raise AssertionError("No debería llamar API si cotización está deshabilitada")

    monkeypatch.setattr("services.correo_argentino_micorreo._obtener_token_y_customer_id", explotar)

    r = cotizar_envio("1000", config=cfg())

    assert r["ok"] is False
    assert "deshabilitada" in r["error"].lower()


def test_consultar_sucursales_no_llama_api_si_funcion_deshabilitada(monkeypatch):
    from services.correo_argentino_micorreo import consultar_sucursales

    monkeypatch.setenv("CORREO_MICORREO_FEATURE_SUCURSALES", "false")

    def explotar(*args, **kwargs):
        raise AssertionError("No debería llamar API si sucursales está deshabilitada")

    monkeypatch.setattr("services.correo_argentino_micorreo._obtener_token_y_customer_id", explotar)

    r = consultar_sucursales("R", config=cfg())

    assert r["ok"] is False
    assert "deshabilitada" in r["error"].lower()


def test_consultar_tracking_no_llama_api_si_funcion_deshabilitada(monkeypatch):
    from services.correo_argentino_micorreo import consultar_tracking_envio

    monkeypatch.setenv("CORREO_MICORREO_FEATURE_TRACKING", "false")

    def explotar(*args, **kwargs):
        raise AssertionError("No debería llamar API si tracking está deshabilitado")

    monkeypatch.setattr("services.correo_argentino_micorreo.obtener_token", explotar)

    r = consultar_tracking_envio("TRACKING_TEST", config=cfg())

    assert r["ok"] is False
    assert "deshabilitada" in r["error"].lower()
