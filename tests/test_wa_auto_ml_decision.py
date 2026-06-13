from services.wa_auto_ml_decision import limpiar_faltantes_para_handoff_wa


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