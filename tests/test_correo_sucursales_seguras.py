from types import SimpleNamespace

from modules.transportes import correo_argentino


def pedido_fake(
    cp="7505",
    localidad="Claromeco",
    provincia="Buenos Aires",
    latitud_cliente=-38.857,
    longitud_cliente=-60.075,
):
    return SimpleNamespace(
        id=875,
        codigo_postal=cp,
        localidad=localidad,
        provincia=provincia,
        direccion="",
        cpa="",
        ubicacion_fuente="pedido_lat_lng",
        ubicacion_confianza="alta",
        latitud_cliente=latitud_cliente,
        longitud_cliente=longitud_cliente,
    )


def agencia(nombre, ciudad, cp, lat, lng, provincia="Buenos Aires"):
    return {
        "agency_id": nombre.upper().replace(" ", "_"),
        "agency_name": nombre,
        "location": {
            "city_name": ciudad,
            "state_name": provincia,
            "zip_code": cp,
            "street_name": "Calle",
            "street_number": "123",
            "geolocation": {
                "latitude": lat,
                "longitude": lng,
            },
        },
        "pickup_availability": True,
    }


def test_correo_no_ofrece_sucursales_solo_por_provincia_si_estan_lejos(monkeypatch):
    monkeypatch.setenv("CORREO_SUCURSALES_RADIO_MAX_KM", "90")

    monkeypatch.setattr(
        correo_argentino,
        "_obtener_sucursales_correo_paqar",
        lambda **kwargs: [
            agencia("SAN MARTIN", "SAN MARTIN", "1650", -34.57, -58.53),
            agencia("TIGRE", "TIGRE", "1648", -34.42, -58.58),
            agencia("VICENTE LOPEZ", "VICENTE LOPEZ", "1638", -34.53, -58.48),
        ],
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake()
    )

    assert resultado == []


def test_correo_devuelve_sucursales_ordenadas_por_distancia_real(monkeypatch):
    monkeypatch.setenv("CORREO_SUCURSALES_RADIO_MAX_KM", "90")

    monkeypatch.setattr(
        correo_argentino,
        "_obtener_sucursales_correo_paqar",
        lambda **kwargs: [
            agencia("SAN CAYETANO", "SAN CAYETANO", "7521", -38.346, -59.609),
            agencia("TRES ARROYOS", "TRES ARROYOS", "7500", -38.3739, -60.2798),
            agencia("SAN MARTIN", "SAN MARTIN", "1650", -34.57, -58.53),
        ],
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake()
    )

    nombres = [s["nombre"] for s in resultado]

    assert nombres == ["TRES ARROYOS", "SAN CAYETANO"]
    assert resultado[0]["distancia_km"] < resultado[1]["distancia_km"]


def test_correo_no_ofrece_si_cliente_no_tiene_coordenadas(monkeypatch):
    monkeypatch.setattr(
        correo_argentino,
        "_obtener_sucursales_correo_paqar",
        lambda **kwargs: [
            agencia("TRES ARROYOS", "TRES ARROYOS", "7500", -38.3739, -60.2798),
        ],
    )

    def fake_normalizar(pedido):
        return {"completados": []}

    monkeypatch.setattr(
        "services.ubicacion_cp.normalizar_ubicacion_pedido",
        fake_normalizar,
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake(
            latitud_cliente=None,
            longitud_cliente=None,
        )
    )

    assert resultado == []


def test_correo_no_ofrece_sucursales_sin_coordenadas_de_sucursal(monkeypatch):
    monkeypatch.setattr(
        correo_argentino,
        "_obtener_sucursales_correo_paqar",
        lambda **kwargs: [
            {
                "agency_id": "TRES_ARROYOS",
                "agency_name": "TRES ARROYOS",
                "location": {
                    "city_name": "TRES ARROYOS",
                    "state_name": "Buenos Aires",
                    "zip_code": "7500",
                    "street_name": "Calle",
                    "street_number": "123",
                    "geolocation": {},
                },
                "pickup_availability": True,
            }
        ],
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake()
    )

    assert resultado == []


def test_correo_fallback_paqar_recibe_state_id_mendoza(monkeypatch):
    capturado = {}

    monkeypatch.setattr(
        "services.correo_argentino_micorreo.consultar_sucursales",
        lambda **kwargs: {
            "ok": False,
            "error": "MiCorreo no disponible",
            "sucursales": [],
        },
    )

    def fake_obtener_paqar(**kwargs):
        capturado.update(kwargs)
        return []

    monkeypatch.setattr(
        correo_argentino,
        "_obtener_sucursales_correo_paqar",
        fake_obtener_paqar,
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake(
            cp="5519",
            localidad="Guaymallen",
            provincia="Mendoza",
        )
    )

    assert resultado == []
    assert capturado == {
        "state_id": "M",
        "pickup_availability": True,
        "package_reception": None,
    }
