from types import SimpleNamespace

from services.sucursales_distancia import (
    distancia_km,
    obtener_coordenadas_cliente_pedido,
    obtener_coordenadas_sucursal,
    ordenar_sucursales_por_distancia,
)


def pedido_cliente(lat=-38.857, lng=-60.075):
    return SimpleNamespace(
        latitud_cliente=lat,
        longitud_cliente=lng,
        ubicacion_fuente="pedido_lat_lng",
        ubicacion_confianza="alta",
        codigo_postal="7505",
        localidad="Claromeco",
        provincia="Buenos Aires",
        cpa="",
    )


def sucursal(nombre, lat=None, lng=None):
    return {
        "id": nombre.upper().replace(" ", "_"),
        "nombre": nombre,
        "lat": lat,
        "lng": lng,
    }


def test_distancia_km_calcula_valor_positivo():
    distancia = distancia_km(-38.857, -60.075, -38.3739, -60.2798)

    assert distancia > 0


def test_obtiene_coordenadas_cliente_desde_pedido():
    resultado = obtener_coordenadas_cliente_pedido(
        pedido_cliente(),
        permitir_normalizar=False,
    )

    assert resultado["ok"] is True
    assert resultado["lat"] == -38.857
    assert resultado["lng"] == -60.075
    assert resultado["fuente"] == "pedido_lat_lng"


def test_obtiene_coordenadas_sucursal_desde_lat_lng():
    lat, lng = obtener_coordenadas_sucursal(
        sucursal("Tres Arroyos", -38.3739, -60.2798)
    )

    assert lat == -38.3739
    assert lng == -60.2798


def test_obtiene_coordenadas_sucursal_desde_raw_geolocation():
    lat, lng = obtener_coordenadas_sucursal({
        "nombre": "Tres Arroyos",
        "raw": {
            "location": {
                "geolocation": {
                    "latitude": -38.3739,
                    "longitude": -60.2798,
                }
            }
        }
    })

    assert lat == -38.3739
    assert lng == -60.2798


def test_ordena_sucursales_por_distancia_real():
    resultado = ordenar_sucursales_por_distancia(
        pedido=pedido_cliente(),
        sucursales=[
            sucursal("San Martin", -34.57, -58.53),
            sucursal("Tres Arroyos", -38.3739, -60.2798),
            sucursal("San Cayetano", -38.346, -59.609),
        ],
        radio_max_km=600,
        limite=3,
        permitir_normalizar_pedido=False,
    )

    nombres = [s["nombre"] for s in resultado["sucursales"]]

    assert resultado["ok"] is True
    assert nombres[0] == "Tres Arroyos"
    assert resultado["sucursales"][0]["distancia_km"] < resultado["sucursales"][1]["distancia_km"]


def test_filtra_sucursales_fuera_del_radio():
    resultado = ordenar_sucursales_por_distancia(
        pedido=pedido_cliente(),
        sucursales=[
            sucursal("San Martin", -34.57, -58.53),
            sucursal("Tres Arroyos", -38.3739, -60.2798),
        ],
        radio_max_km=90,
        limite=3,
        permitir_normalizar_pedido=False,
    )

    nombres = [s["nombre"] for s in resultado["sucursales"]]

    assert "Tres Arroyos" in nombres
    assert "San Martin" not in nombres


def test_no_devuelve_sucursales_si_cliente_no_tiene_coordenadas():
    resultado = ordenar_sucursales_por_distancia(
        pedido=pedido_cliente(lat=None, lng=None),
        sucursales=[
            sucursal("Tres Arroyos", -38.3739, -60.2798),
        ],
        radio_max_km=90,
        limite=3,
        permitir_normalizar_pedido=False,
    )

    assert resultado["ok"] is False
    assert resultado["sucursales"] == []
    assert resultado["motivo"] == "sin_coordenadas_cliente"


def test_puede_normalizar_pedido_si_no_tiene_coordenadas(monkeypatch):
    pedido = pedido_cliente(lat=None, lng=None)

    def fake_normalizar(p):
        p.latitud_cliente = -38.857
        p.longitud_cliente = -60.075
        p.ubicacion_fuente = "test_normalizado"
        p.ubicacion_confianza = "alta"
        return {"completados": ["latitud_cliente", "longitud_cliente"]}

    monkeypatch.setattr(
        "services.ubicacion_cp.normalizar_ubicacion_pedido",
        fake_normalizar,
    )

    resultado = ordenar_sucursales_por_distancia(
        pedido=pedido,
        sucursales=[
            sucursal("Tres Arroyos", -38.3739, -60.2798),
        ],
        radio_max_km=90,
        limite=3,
    )

    assert resultado["ok"] is True
    assert resultado["cliente"]["fuente"] == "test_normalizado"
