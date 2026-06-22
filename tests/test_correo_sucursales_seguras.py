from types import SimpleNamespace

from modules.transportes import correo_argentino


def pedido_fake(cp="7505", localidad="Claromeco", provincia="Buenos Aires"):
    return SimpleNamespace(
        codigo_postal=cp,
        localidad=localidad,
        provincia=provincia,
        direccion="",
    )


def agencia(nombre, ciudad, cp, provincia="Buenos Aires"):
    return {
        "agency_id": nombre.upper().replace(" ", "_"),
        "agency_name": nombre,
        "location": {
            "city_name": ciudad,
            "state_name": provincia,
            "zip_code": cp,
            "street_name": "Calle",
            "street_number": "123",
            "geolocation": {},
        },
        "pickup_availability": True,
    }


def test_correo_no_ofrece_sucursales_solo_por_provincia(monkeypatch):
    monkeypatch.setattr(
        correo_argentino,
        "obtener_sucursales_correo",
        lambda **kwargs: [
            agencia("SAN MARTIN", "SAN MARTIN", "1650"),
            agencia("TIGRE", "TIGRE", "1648"),
            agencia("VICENTE LOPEZ", "VICENTE LOPEZ", "1638"),
        ],
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake(cp="7505", localidad="Claromeco", provincia="Buenos Aires")
    )

    assert resultado == []


def test_correo_ofrece_sucursal_con_cp_exacto(monkeypatch):
    monkeypatch.setattr(
        correo_argentino,
        "obtener_sucursales_correo",
        lambda **kwargs: [
            agencia("SAN MARTIN", "SAN MARTIN", "1650"),
            agencia("CLAROMECO", "CLAROMECO", "7505"),
        ],
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake(cp="7505", localidad="Claromeco", provincia="Buenos Aires")
    )

    assert len(resultado) == 1
    assert resultado[0]["nombre"] == "CLAROMECO"


def test_correo_ofrece_sucursal_con_localidad_confiable(monkeypatch):
    monkeypatch.setattr(
        correo_argentino,
        "obtener_sucursales_correo",
        lambda **kwargs: [
            agencia("SAN MARTIN", "SAN MARTIN", "1650"),
            agencia("TRES ARROYOS", "TRES ARROYOS", "7500"),
        ],
    )

    resultado = correo_argentino.obtener_sucursales_correo_por_pedido(
        pedido_fake(cp="7505", localidad="Tres Arroyos", provincia="Buenos Aires")
    )

    assert len(resultado) == 1
    assert resultado[0]["nombre"] == "TRES ARROYOS"
