import json

from services.correo_sucursales_eleccion import detectar_sucursal_correo_ofrecida


class PedidoCorreoFake:
    def __init__(self):
        self.correo_sucursales_ofrecidas = json.dumps([
            {
                "id": "R0100",
                "nombre": "Correo Centro",
                "direccion": "San Martin 100",
                "localidad": "Bariloche",
                "provincia": "Rio Negro",
                "postalCode": "8400",
            },
            {
                "id": "R0101",
                "nombre": "Correo Mitre",
                "direccion": "Mitre 500",
                "localidad": "Bariloche",
                "provincia": "Rio Negro",
                "postalCode": "8400",
            },
            {
                "id": "R0102",
                "nombre": "Correo Moreno",
                "direccion": "Moreno 700",
                "localidad": "Bariloche",
                "provincia": "Rio Negro",
                "postalCode": "8400",
            },
            {
                "id": "R0103",
                "nombre": "Correo Onelli",
                "direccion": "Onelli 900",
                "localidad": "Bariloche",
                "provincia": "Rio Negro",
                "postalCode": "8400",
            },
        ], ensure_ascii=False)


def test_detecta_sucursal_correo_por_numero():
    pedido = PedidoCorreoFake()

    sucursal = detectar_sucursal_correo_ofrecida(pedido, "la 2")

    assert sucursal["nombre"] == "Correo Mitre"
    assert sucursal["direccion"] == "Mitre 500"
    assert sucursal["localidad"] == "Bariloche"
    assert sucursal["provincia"] == "Rio Negro"
    assert sucursal["cp"] == "8400"


def test_detecta_sucursal_correo_por_cuarta_opcion():
    pedido = PedidoCorreoFake()

    sucursal = detectar_sucursal_correo_ofrecida(pedido, "prefiero la cuarta")

    assert sucursal["nombre"] == "Correo Onelli"


def test_detecta_sucursal_correo_por_nombre():
    pedido = PedidoCorreoFake()

    sucursal = detectar_sucursal_correo_ofrecida(pedido, "me quedo con la de moreno")

    assert sucursal["nombre"] == "Correo Moreno"


def test_detecta_sucursal_correo_sin_ofrecidas_devuelve_none():
    pedido = PedidoCorreoFake()
    pedido.correo_sucursales_ofrecidas = ""

    assert detectar_sucursal_correo_ofrecida(pedido, "la 1") is None
