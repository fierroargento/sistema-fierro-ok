import sys
from types import SimpleNamespace

import modules.transportes.selector as selector


class ItemFalso:
    def __init__(self, sku, descripcion, cantidad):
        self.sku = sku
        self.descripcion = descripcion
        self.cantidad = cantidad


class PedidoFalso:
    def __init__(self, cp="7505", items=None):
        self.codigo_postal = cp
        self.items = items or []


class ProductoFalso:
    def __init__(
        self,
        peso_gr,
        alto_cm,
        ancho_cm,
        largo_cm,
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


class QueryProductoFalsa:
    def __init__(self, catalogo):
        self.catalogo = catalogo
        self.sku = ""

    def filter_by(self, sku):
        self.sku = sku
        return self

    def first(self):
        return self.catalogo.get(self.sku)


def instalar_catalogo_fake(monkeypatch, catalogo):
    class ProductoModeloFalso:
        pass

    ProductoModeloFalso.query = QueryProductoFalsa(catalogo)

    monkeypatch.setitem(
        sys.modules,
        "app",
        SimpleNamespace(Producto=ProductoModeloFalso),
    )


def test_cotizar_correo_pp6040_usa_dimensiones_del_catalogo(monkeypatch):
    instalar_catalogo_fake(monkeypatch, {
        "PP6040H": ProductoFalso(
            peso_gr=3200,
            alto_cm=5,
            ancho_cm=42,
            largo_cm=36,
        )
    })

    llamadas = []

    def cotizador_fake(cp, tipo_entrega="S", **kwargs):
        llamadas.append({
            "cp": cp,
            "tipo_entrega": tipo_entrega,
            **kwargs,
        })
        return {
            "disponible": True,
            "precio": 1000 if tipo_entrega == "S" else 1500,
            "tipo": "correo_argentino",
            "servicio": "MiCorreo",
            "error": None,
        }

    monkeypatch.setattr(selector, "cotizar_correo", cotizador_fake)

    pedido = PedidoFalso(items=[
        ItemFalso("PP6040H", "Parrilla plegable", 2),
    ])

    resultado = selector.cotizar_correo_pp6040(pedido)

    assert resultado["ok"] is True
    assert resultado["dimensiones"] == {
        "peso_gr": 6400.0,
        "alto_cm": 10.0,
        "ancho_cm": 42.0,
        "largo_cm": 36.0,
    }

    assert len(llamadas) == 2
    assert llamadas[0]["tipo_entrega"] == "S"
    assert llamadas[1]["tipo_entrega"] == "D"

    for llamada in llamadas:
        assert llamada["peso_gr"] == 6400.0
        assert llamada["alto_cm"] == 10.0
        assert llamada["ancho_cm"] == 42.0
        assert llamada["largo_cm"] == 36.0


def test_cotizar_correo_pp6040_escala_si_falta_catalogo(monkeypatch):
    instalar_catalogo_fake(monkeypatch, {})

    llamadas = []

    def cotizador_fake(*args, **kwargs):
        llamadas.append((args, kwargs))
        return {"disponible": True, "precio": 1}

    monkeypatch.setattr(selector, "cotizar_correo", cotizador_fake)

    pedido = PedidoFalso(items=[
        ItemFalso("SINCAT", "Producto sin catálogo", 1),
    ])

    resultado = selector.cotizar_correo_pp6040(pedido)

    assert resultado["ok"] is False
    assert resultado["requiere_operador"] is True
    assert "Datos logísticos incompletos" in resultado["error"]
    assert "SKU SINCAT no encontrado en catálogo." in resultado["error"]
    assert llamadas == []


def test_cotizar_correo_pp6040_escala_si_producto_no_permite_correo(monkeypatch):
    instalar_catalogo_fake(monkeypatch, {
        "CUADRO01": ProductoFalso(
            peso_gr=500,
            alto_cm=3,
            ancho_cm=30,
            largo_cm=40,
            permite_correo=False,
        )
    })

    monkeypatch.setattr(
        selector,
        "cotizar_correo",
        lambda *args, **kwargs: {"disponible": True, "precio": 1},
    )

    pedido = PedidoFalso(items=[
        ItemFalso("CUADRO01", "Cuadro", 1),
    ])

    resultado = selector.cotizar_correo_pp6040(pedido)

    assert resultado["ok"] is False
    assert resultado["motivo"] == "producto_no_permite_correo"
    assert "no permite Correo Argentino" in resultado["error"]
