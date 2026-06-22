from services.productos_logistica import (
    calcular_logistica_pedido,
    producto_tiene_logistica_completa,
)


class ItemFalso:
    def __init__(self, sku, descripcion, cantidad):
        self.sku = sku
        self.descripcion = descripcion
        self.cantidad = cantidad


class PedidoFalso:
    def __init__(self, items):
        self.items = items


class ProductoFalso:
    def __init__(
        self,
        peso_gr=None,
        alto_cm=None,
        ancho_cm=None,
        largo_cm=None,
        permite_correo=True,
        permite_via_cargo=True,
        requiere_revision_logistica=False,
    ):
        self.peso_gr = peso_gr
        self.alto_cm = alto_cm
        self.ancho_cm = ancho_cm
        self.largo_cm = largo_cm
        self.permite_correo = permite_correo
        self.permite_via_cargo = permite_via_cargo
        self.requiere_revision_logistica = requiere_revision_logistica


def test_calcular_logistica_pedido_con_parrillas_apiladas():
    pedido = PedidoFalso([
        ItemFalso("PP6040H", "Parrilla plegable", 2),
    ])

    catalogo = {
        "PP6040H": ProductoFalso(
            peso_gr=3200,
            alto_cm=5,
            ancho_cm=42,
            largo_cm=36,
        )
    }

    resultado = calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: catalogo.get(sku),
    )

    assert resultado["ok"] is True
    assert resultado["peso_gr"] == 6400
    assert resultado["alto_cm"] == 10
    assert resultado["ancho_cm"] == 42
    assert resultado["largo_cm"] == 36
    assert resultado["permite_correo"] is True
    assert resultado["permite_via_cargo"] is True
    assert resultado["requiere_revision_logistica"] is False
    assert resultado["faltantes"] == []


def test_calcular_logistica_pedido_detecta_sku_sin_catalogo():
    pedido = PedidoFalso([
        ItemFalso("SINCAT", "Producto sin catálogo", 1),
    ])

    resultado = calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: None,
    )

    assert resultado["ok"] is False
    assert resultado["motivo"] == "datos_logisticos_incompletos"
    assert resultado["permite_correo"] is False
    assert resultado["requiere_revision_logistica"] is True
    assert "SKU SINCAT no encontrado en catálogo." in resultado["faltantes"]


def test_calcular_logistica_pedido_detecta_datos_incompletos():
    pedido = PedidoFalso([
        ItemFalso("PP6040H", "Parrilla plegable", 1),
    ])

    catalogo = {
        "PP6040H": ProductoFalso(
            peso_gr=3200,
            alto_cm=5,
            ancho_cm=None,
            largo_cm=36,
        )
    }

    resultado = calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: catalogo.get(sku),
    )

    assert resultado["ok"] is False
    assert resultado["peso_gr"] is None
    assert resultado["permite_correo"] is False
    assert resultado["requiere_revision_logistica"] is True
    assert "SKU PP6040H sin datos logísticos completos: ancho_cm." in resultado["faltantes"]


def test_calcular_logistica_pedido_respeta_permisos_transporte():
    pedido = PedidoFalso([
        ItemFalso("CUADRO01", "Cuadro", 1),
    ])

    catalogo = {
        "CUADRO01": ProductoFalso(
            peso_gr=500,
            alto_cm=3,
            ancho_cm=30,
            largo_cm=40,
            permite_correo=False,
            permite_via_cargo=True,
        )
    }

    resultado = calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: catalogo.get(sku),
    )

    assert resultado["ok"] is True
    assert resultado["permite_correo"] is False
    assert resultado["permite_via_cargo"] is True


def test_calcular_logistica_pedido_con_productos_mixtos():
    pedido = PedidoFalso([
        ItemFalso("PP6040H", "Parrilla", 1),
        ItemFalso("KIT001", "Kit pala", 2),
    ])

    catalogo = {
        "PP6040H": ProductoFalso(
            peso_gr=3200,
            alto_cm=5,
            ancho_cm=42,
            largo_cm=36,
        ),
        "KIT001": ProductoFalso(
            peso_gr=900,
            alto_cm=4,
            ancho_cm=12,
            largo_cm=60,
        ),
    }

    resultado = calcular_logistica_pedido(
        pedido,
        buscar_producto_por_sku=lambda sku: catalogo.get(sku),
    )

    assert resultado["ok"] is True
    assert resultado["peso_gr"] == 5000
    assert resultado["alto_cm"] == 13
    assert resultado["ancho_cm"] == 42
    assert resultado["largo_cm"] == 60


def test_producto_tiene_logistica_completa():
    completo = ProductoFalso(
        peso_gr=1000,
        alto_cm=10,
        ancho_cm=20,
        largo_cm=30,
    )

    incompleto = ProductoFalso(
        peso_gr=1000,
        alto_cm=None,
        ancho_cm=20,
        largo_cm=30,
    )

    assert producto_tiene_logistica_completa(completo) is True
    assert producto_tiene_logistica_completa(incompleto) is False
