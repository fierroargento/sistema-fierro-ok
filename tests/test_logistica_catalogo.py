from types import SimpleNamespace

from services.logistica_catalogo import (
    buscar_producto_catalogo_por_sku,
    calcular_logistica_pedido_desde_catalogo,
)


class QueryFake:
    def __init__(self, productos):
        self.productos = productos
        self.sku_busqueda = None

    def filter_by(self, sku):
        self.sku_busqueda = sku
        return self

    def first(self):
        return self.productos.get(self.sku_busqueda)


class ProductoFake:
    query = QueryFake({})


class ItemFake:
    def __init__(self, sku, cantidad=1):
        self.sku = sku
        self.cantidad = cantidad


class PedidoFake:
    def __init__(self, items):
        self.items = items


def test_buscar_producto_catalogo_por_sku_normaliza_sku():
    producto = SimpleNamespace(sku="PF9060H")
    ProductoFake.query = QueryFake({"PF9060H": producto})

    encontrado = buscar_producto_catalogo_por_sku(ProductoFake, " pf9060h ")

    assert encontrado is producto


def test_calcular_logistica_pedido_desde_catalogo_usa_producto_inyectado():
    producto = SimpleNamespace(
        sku="PF9060H",
        peso_gr=8500,
        alto_cm=12,
        ancho_cm=60,
        largo_cm=90,
        permite_correo=True,
    )
    ProductoFake.query = QueryFake({"PF9060H": producto})

    pedido = PedidoFake([ItemFake("PF9060H", cantidad=1)])

    resultado = calcular_logistica_pedido_desde_catalogo(
        pedido,
        Producto=ProductoFake,
    )

    assert resultado["ok"] is True
    assert resultado["peso_gr"] == 8500
    assert resultado["alto_cm"] == 12
    assert resultado["ancho_cm"] == 60
    assert resultado["largo_cm"] == 90
    assert resultado["permite_correo"] is True
