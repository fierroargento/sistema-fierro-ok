from services.ia_recolector_sync import (
    calcular_faltantes_reales_recolector,
    consolidar_datos_recolector_con_pedido,
    ia_cp_valido_recolector,
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
        self.ml_billing_documento = ""
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


def test_ia_cp_valido_recolector_acepta_cp_normal():
    assert ia_cp_valido_recolector("6620") == "6620"


def test_ia_cp_valido_recolector_rechaza_vacio_o_muy_corto():
    assert ia_cp_valido_recolector("") == ""
    assert ia_cp_valido_recolector("12") == ""


def test_calcular_faltantes_reales_recolector_sin_faltantes_con_pedido_completo():
    pedido = PedidoFake()

    faltantes = calcular_faltantes_reales_recolector(pedido, {})

    assert faltantes == []


def test_calcular_faltantes_reales_recolector_usa_telefono_detectado():
    pedido = PedidoFake()
    pedido.telefono = ""

    faltantes = calcular_faltantes_reales_recolector(
        pedido,
        {"telefono": "2346513896"},
    )

    assert "telefono" not in faltantes


def test_calcular_faltantes_reales_recolector_falta_telefono_si_no_esta_en_pedido_ni_datos():
    pedido = PedidoFake()
    pedido.telefono = ""

    faltantes = calcular_faltantes_reales_recolector(pedido, {})

    assert "telefono" in faltantes


def test_calcular_faltantes_reales_recolector_falta_cp_y_localidad_si_no_hay_ninguno():
    pedido = PedidoFake()
    pedido.codigo_postal = ""
    pedido.localidad = ""

    faltantes = calcular_faltantes_reales_recolector(pedido, {})

    assert "codigo_postal" in faltantes
    assert "localidad" in faltantes


def test_calcular_faltantes_reales_recolector_cp_valido_no_pide_localidad():
    pedido = PedidoFake()
    pedido.codigo_postal = "6620"
    pedido.localidad = ""

    faltantes = calcular_faltantes_reales_recolector(pedido, {})

    assert "codigo_postal" not in faltantes
    assert "localidad" not in faltantes


def test_calcular_faltantes_reales_recolector_ml_billing_documento_cubre_dni():
    pedido = PedidoFake()
    pedido.dni = ""
    pedido.ml_billing_documento = "31991373"

    faltantes = calcular_faltantes_reales_recolector(pedido, {})

    assert "dni" not in faltantes


def test_decidir_estado_recolector_requiere_operador_prioriza():
    from services.ia_recolector_sync import decidir_estado_recolector

    assert decidir_estado_recolector(
        faltantes=[],
        requiere_operador=True,
    ) == "requiere_operador"


def test_decidir_estado_recolector_datos_completos_sin_faltantes():
    from services.ia_recolector_sync import decidir_estado_recolector

    assert decidir_estado_recolector(
        faltantes=[],
        requiere_operador=False,
    ) == "datos_completos"


def test_decidir_estado_recolector_juntando_datos_con_faltantes():
    from services.ia_recolector_sync import decidir_estado_recolector

    assert decidir_estado_recolector(
        faltantes=["telefono"],
        requiere_operador=False,
    ) == "juntando_datos"


def test_json_loads_seguro_recolector_parsea_json_valido():
    from services.ia_recolector_sync import json_loads_seguro_recolector

    assert json_loads_seguro_recolector("{\"telefono\": \"123\"}") == {
        "telefono": "123",
    }


def test_json_loads_seguro_recolector_extrae_json_embebido():
    from services.ia_recolector_sync import json_loads_seguro_recolector

    assert json_loads_seguro_recolector("texto previo {\"a\": 1} texto posterior") == {
        "a": 1,
    }


def test_json_loads_seguro_recolector_devuelve_dict_vacio_si_falla():
    from services.ia_recolector_sync import json_loads_seguro_recolector

    assert json_loads_seguro_recolector("no es json") == {}


def test_datos_detectados_pedido_recolector_devuelve_dict():
    from services.ia_recolector_sync import datos_detectados_pedido_recolector

    pedido = PedidoFake()
    pedido.ia_datos_detectados = "{\"telefono\": \"5492346513896\"}"

    assert datos_detectados_pedido_recolector(pedido) == {
        "telefono": "5492346513896",
    }


def test_datos_detectados_pedido_recolector_descarta_no_dict():
    from services.ia_recolector_sync import datos_detectados_pedido_recolector

    pedido = PedidoFake()
    pedido.ia_datos_detectados = "[\"telefono\"]"

    assert datos_detectados_pedido_recolector(pedido) == {}


def test_faltantes_pedido_recolector_devuelve_lista():
    from services.ia_recolector_sync import faltantes_pedido_recolector

    pedido = PedidoFake()
    pedido.ia_faltantes = "[\"telefono\", \"direccion\"]"

    assert faltantes_pedido_recolector(pedido) == [
        "telefono",
        "direccion",
    ]


def test_faltantes_pedido_recolector_descarta_no_lista():
    from services.ia_recolector_sync import faltantes_pedido_recolector

    pedido = PedidoFake()
    pedido.ia_faltantes = "{\"telefono\": true}"

    assert faltantes_pedido_recolector(pedido) == []

def test_marcar_recolector_datos_completos():
    from types import SimpleNamespace

    from services.ia_recolector_sync import (
        marcar_recolector_datos_completos,
    )

    pedido = SimpleNamespace(
        ia_faltantes='["telefono"]',
        ia_recolector_estado="juntando_datos",
        ia_ultimo_timeout_operador="pendiente",
    )

    resultado = marcar_recolector_datos_completos(
        pedido,
    )

    assert resultado is True
    assert pedido.ia_faltantes == "[]"
    assert (
        pedido.ia_recolector_estado
        == "datos_completos"
    )
    assert pedido.ia_ultimo_timeout_operador is None


def test_marcar_recolector_datos_completos_sin_pedido():
    from services.ia_recolector_sync import (
        marcar_recolector_datos_completos,
    )

    assert (
        marcar_recolector_datos_completos(None)
        is False
    )
