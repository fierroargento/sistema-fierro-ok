from services.wa_auto_ml_decision import (
    agregar_marca_a_resumen_si_falta,
    construir_marca_ml_sigue_recolectando,
    limpiar_faltantes_para_handoff_wa,
)


class PedidoFake:
    def __init__(self, localidad="", provincia=""):
        self.localidad = localidad
        self.provincia = provincia


def test_limpiar_faltantes_elimina_vacios():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["", None, "dni"],
        telefono_normalizado="",
    )

    assert resultado == ["dni"]


def test_limpiar_faltantes_elimina_telefono_si_ya_hay_telefono_normalizado():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["telefono", "dni"],
        telefono_normalizado="5492920123456",
    )

    assert resultado == ["dni"]


def test_limpiar_faltantes_mantiene_telefono_si_no_hay_telefono_normalizado():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["telefono", "dni"],
        telefono_normalizado="",
    )

    assert resultado == ["telefono", "dni"]


def test_limpiar_faltantes_elimina_localidad_y_provincia_si_ya_existen():
    pedido = PedidoFake(localidad="Viedma", provincia="Rio Negro")

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["localidad", "provincia", "direccion"],
        telefono_normalizado="",
    )

    assert resultado == ["direccion"]


def test_limpiar_faltantes_deduplica_manteniendo_orden():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=["dni", "telefono", "dni", "direccion", "telefono"],
        telefono_normalizado="",
    )

    assert resultado == ["dni", "telefono", "direccion"]


def test_limpiar_faltantes_devuelve_lista_vacia_sin_faltantes():
    pedido = PedidoFake()

    resultado = limpiar_faltantes_para_handoff_wa(
        pedido,
        faltantes=None,
        telefono_normalizado="",
    )

    assert resultado == []

def test_construir_marca_ml_sigue_recolectando_con_faltantes():
    marca = construir_marca_ml_sigue_recolectando(["dni", "direccion"])

    assert marca == (
        "ML sigue recolectando datos; WA no iniciado por faltantes: "
        "dni, direccion"
    )


def test_construir_marca_ml_sigue_recolectando_limpia_vacios():
    marca = construir_marca_ml_sigue_recolectando(["dni", "", None, "telefono"])

    assert marca == (
        "ML sigue recolectando datos; WA no iniciado por faltantes: "
        "dni, telefono"
    )


def test_construir_marca_ml_sigue_recolectando_sin_faltantes():
    marca = construir_marca_ml_sigue_recolectando([])

    assert marca == "ML sigue recolectando datos; WA no iniciado por faltantes"

def test_agregar_marca_a_resumen_si_falta_agrega_con_separador():
    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo",
        "Marca nueva",
    )

    assert resultado == "Resumen previo | Marca nueva"


def test_agregar_marca_a_resumen_si_falta_no_duplica():
    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo | Marca nueva",
        "Marca nueva",
    )

    assert resultado == "Resumen previo | Marca nueva"


def test_agregar_marca_a_resumen_si_falta_soporta_resumen_vacio():
    resultado = agregar_marca_a_resumen_si_falta(
        "",
        "Marca nueva",
    )

    assert resultado == "Marca nueva"


def test_agregar_marca_a_resumen_si_falta_ignora_marca_vacia():
    resultado = agregar_marca_a_resumen_si_falta(
        "Resumen previo",
        "",
    )

    assert resultado == "Resumen previo"


def test_agregar_marca_a_resumen_si_falta_respeta_limite():
    resultado = agregar_marca_a_resumen_si_falta(
        "A" * 20,
        "B" * 20,
        limite=10,
    )

    assert resultado == "A" * 10
