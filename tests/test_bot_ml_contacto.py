from modules.bot_ml.contacto import (
    generar_mensaje_contacto_ml,
    pedido_es_plegable_pp6040,
)


class ItemFake:
    def __init__(self, sku="", descripcion=""):
        self.sku = sku
        self.descripcion = descripcion


class PedidoFake:
    def __init__(self, items=None):
        self.items = items or []


def es_acordas_true(pedido):
    return True


def es_acordas_false(pedido):
    return False


def test_pedido_es_plegable_pp6040_detecta_por_sku():
    pedido = PedidoFake(items=[
        ItemFake(sku="PP6040H", descripcion="Parrilla"),
    ])

    assert pedido_es_plegable_pp6040(pedido) is True


def test_pedido_es_plegable_pp6040_detecta_por_descripcion():
    pedido = PedidoFake(items=[
        ItemFake(sku="", descripcion="Parrilla plegable"),
    ])

    assert pedido_es_plegable_pp6040(pedido) is True


def test_pedido_es_plegable_pp6040_false_si_no_coincide():
    pedido = PedidoFake(items=[
        ItemFake(sku="KIT001", descripcion="Kit pala y atizador"),
    ])

    assert pedido_es_plegable_pp6040(pedido) is False


def test_generar_mensaje_contacto_ml_no_aplica_si_no_es_acordas():
    pedido = PedidoFake(items=[
        ItemFake(sku="PP6040H", descripcion="Parrilla"),
    ])

    assert generar_mensaje_contacto_ml(pedido, es_acordas_false) == ""


def test_generar_mensaje_contacto_ml_pp6040_pide_datos_sin_sucursal():
    pedido = PedidoFake(items=[
        ItemFake(sku="PP6040H", descripcion="Parrilla"),
    ])

    texto = generar_mensaje_contacto_ml(pedido, es_acordas_true)

    assert "Nombre completo de quien recibe" in texto
    assert "Telefono de contacto" in texto
    assert "sucursal Via Cargo" not in texto
    assert len(texto) <= 348


def test_generar_mensaje_contacto_ml_no_pp6040_menciona_sucursal_via_cargo():
    pedido = PedidoFake(items=[
        ItemFake(sku="BR001", descripcion="Brasero"),
    ])

    texto = generar_mensaje_contacto_ml(pedido, es_acordas_true)

    assert "sucursal Via Cargo" in texto
    assert "Nombre completo" in texto
    assert len(texto) <= 348