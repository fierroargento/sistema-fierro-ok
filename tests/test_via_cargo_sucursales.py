from types import SimpleNamespace

from services.via_cargo_sucursales import (
    filtrar_candidatas_via_cargo,
    seleccionar_sucursales_via_cargo_pedido,
)


def pedido_fake(
    cp="7505",
    localidad="Claromeco",
    provincia="Buenos Aires",
    lat=-38.857,
    lng=-60.075,
):
    return SimpleNamespace(
        codigo_postal=cp,
        localidad=localidad,
        provincia=provincia,
        latitud_cliente=lat,
        longitud_cliente=lng,
        ubicacion_fuente="pedido_lat_lng",
        ubicacion_confianza="alta",
    )


def sucursal(nombre, cp, localidad, provincia, lat=None, lng=None):
    return {
        "id": nombre.upper().replace(" ", "_"),
        "nombre": nombre,
        "cp": cp,
        "localidad": localidad,
        "provincia": provincia,
        "direccion": "Calle 123",
        "lat": lat,
        "lng": lng,
    }


def data_sucursales():
    return [
        sucursal("SAN MARTIN", "1650", "SAN MARTIN", "Buenos Aires", -34.57, -58.53),
        sucursal("TRES ARROYOS", "7500", "TRES ARROYOS", "Buenos Aires", -38.3739, -60.2798),
        sucursal("SAN CAYETANO", "7521", "SAN CAYETANO", "Buenos Aires", -38.346, -59.609),
        sucursal("CORDOBA", "5000", "CORDOBA", "Cordoba", -31.4167, -64.1833),
    ]


def test_filtra_por_cp_exacto_si_existe():
    pedido = pedido_fake(cp="7500", localidad="Tres Arroyos")
    candidatas = filtrar_candidatas_via_cargo(pedido, data_sucursales())

    assert [s["nombre"] for s in candidatas] == ["TRES ARROYOS"]


def test_si_no_hay_cp_exacta_usa_provincia_como_universo_y_distancia_decide():
    resultado = seleccionar_sucursales_via_cargo_pedido(
        pedido_fake(cp="7505", localidad="Claromeco"),
        sucursales=data_sucursales(),
        radio_max_km=90,
        limite=3,
        exigir_distancia=True,
        permitir_normalizar_pedido=False,
    )

    nombres = [s["nombre"] for s in resultado]

    assert nombres == ["TRES ARROYOS", "SAN CAYETANO"]


def test_no_devuelve_sucursales_lejanas_si_hay_radio():
    resultado = seleccionar_sucursales_via_cargo_pedido(
        pedido_fake(cp="7505", localidad="Claromeco"),
        sucursales=data_sucursales(),
        radio_max_km=90,
        limite=3,
        exigir_distancia=True,
        permitir_normalizar_pedido=False,
    )

    nombres = [s["nombre"] for s in resultado]

    assert "SAN MARTIN" not in nombres
    assert "CORDOBA" not in nombres


def test_no_devuelve_si_no_hay_coordenadas_y_exige_distancia():
    resultado = seleccionar_sucursales_via_cargo_pedido(
        pedido_fake(cp="7505", localidad="Claromeco", lat=None, lng=None),
        sucursales=data_sucursales(),
        radio_max_km=90,
        limite=3,
        exigir_distancia=True,
        permitir_normalizar_pedido=False,
    )

    assert resultado == []


def test_modo_compatibilidad_devuelve_candidatas_si_no_puede_distancia():
    resultado = seleccionar_sucursales_via_cargo_pedido(
        pedido_fake(cp="7505", localidad="Claromeco", lat=None, lng=None),
        sucursales=data_sucursales(),
        radio_max_km=90,
        limite=2,
        exigir_distancia=False,
        permitir_normalizar_pedido=False,
    )

    assert len(resultado) == 2
