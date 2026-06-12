from services.ia_recolector_sync import (
    consolidar_datos_recolector_con_pedido,
    persistir_telefono_detectado_recolector,
)


class PedidoFake:
    def __init__(self):
        self.cliente = "Javier Zubillaga"
        self.dni = "40859997"
        self.telefono = "5492314414526"
        self.direccion = "Calle 36 N° 1381 Piso 1 Depto A"
        self.localidad = "La Plata"
        self.provincia = "Buenos Aires"
        self.codigo_postal = "1900"
        self.autorizado_nombre = ""
        self.autorizado_dni = ""
        self.autorizado_telefono = ""


def test_consolidar_datos_recolector_completa_cp_desde_pedido():
    pedido = PedidoFake()
    datos = {
        "nombre": "Javier",
        "apellido": "Zubillaga",
        "dni": "40859997",
        "telefono": "2314414526",
        "direccion": "Calle 36 N° 1381",
        "localidad": "La Plata",
        "codigo_postal": "",
    }

    resultado = consolidar_datos_recolector_con_pedido(pedido, datos)

    assert resultado["codigo_postal"] == "1900"
    assert resultado["provincia"] == "Buenos Aires"
    assert resultado["direccion"] == "Calle 36 N° 1381 Piso 1 Depto A"


def test_consolidar_datos_recolector_no_inventa_si_pedido_no_tiene_cp():
    pedido = PedidoFake()
    pedido.codigo_postal = ""

    resultado = consolidar_datos_recolector_con_pedido(pedido, {})

    assert resultado.get("codigo_postal", "") == ""


def test_consolidar_datos_recolector_respeta_nombre_detectado():
    pedido = PedidoFake()
    datos = {
        "nombre": "Javi",
        "apellido": "Z",
    }

    resultado = consolidar_datos_recolector_con_pedido(pedido, datos)

    assert resultado["nombre"] == "Javi"
    assert resultado["apellido"] == "Z"


def test_persistir_telefono_detectado_recolector_completa_pedido_vacio():
    pedido = PedidoFake()
    pedido.telefono = ""

    datos = {
        "telefono": "2346513896",
    }

    completados = persistir_telefono_detectado_recolector(pedido, datos)

    assert completados == ["telefono"]
    assert pedido.telefono == "5492346513896"
    assert datos["telefono"] == "5492346513896"


def test_persistir_telefono_detectado_recolector_no_pisa_telefono_existente():
    pedido = PedidoFake()
    pedido.telefono = "5492314414526"

    datos = {
        "telefono": "2346513896",
    }

    completados = persistir_telefono_detectado_recolector(pedido, datos)

    assert completados == []
    assert pedido.telefono == "5492314414526"
    assert datos["telefono"] == "2346513896"


def test_persistir_telefono_detectado_recolector_no_inventa_si_no_hay_telefono():
    pedido = PedidoFake()
    pedido.telefono = ""

    datos = {}

    completados = persistir_telefono_detectado_recolector(pedido, datos)

    assert completados == []
    assert pedido.telefono == ""
    assert "telefono" not in datos
