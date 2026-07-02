"""
tests/test_productos_pp6040.py

Regla APB:
- La familia PP6040 se detecta solo por SKU.
- Si el SKU contiene PP6040, aplica regla PP6040.
- No se mira descripciÃ³n ni observaciones.
- PA9060H no debe entrar en regla PP6040.
"""

from types import SimpleNamespace

from domain.productos import (
    normalizar_sku,
    es_sku_pp6040,
    pedido_tiene_pp6040,
)
from modules.transportes.selector import pedido_contiene_pp6040
from services.logistica_defaults import pedido_es_plegable_pp6040_service


def item(sku, descripcion=""):
    return SimpleNamespace(sku=sku, descripcion=descripcion)


def pedido(*items):
    return SimpleNamespace(items=list(items))


def test_normalizar_sku():
    assert normalizar_sku(" pp6040h ") == "PP6040H"
    assert normalizar_sku(None) == ""
    assert normalizar_sku("") == ""


def test_es_sku_pp6040_detecta_pp6040_base():
    assert es_sku_pp6040("PP6040") is True


def test_es_sku_pp6040_detecta_pp6040h():
    assert es_sku_pp6040("PP6040H") is True


def test_es_sku_pp6040_detecta_sku_con_prefijo_o_sufijo():
    assert es_sku_pp6040("ML-PP6040H") is True
    assert es_sku_pp6040("SKU-PP6040") is True


def test_es_sku_pp6040_no_detecta_pa9060h():
    assert es_sku_pp6040("PA9060H") is False


def test_es_sku_pp6040_no_detecta_otros_pa():
    assert es_sku_pp6040("PA6060H") is False
    assert es_sku_pp6040("PA12060H") is False


def test_pedido_tiene_pp6040_true_si_item_sku_contiene_pp6040():
    p = pedido(item("PP6040H"))
    assert pedido_tiene_pp6040(p) is True


def test_pedido_tiene_pp6040_false_para_pa9060h():
    p = pedido(item("PA9060H"))
    assert pedido_tiene_pp6040(p) is False


def test_pedido_tiene_pp6040_no_mira_descripcion_plegable():
    p = pedido(item("PA9060H", descripcion="Parrilla plegable 90x60"))
    assert pedido_tiene_pp6040(p) is False


def test_pedido_tiene_pp6040_false_sin_items():
    assert pedido_tiene_pp6040(SimpleNamespace(items=[])) is False
    assert pedido_tiene_pp6040(SimpleNamespace(items=None)) is False
    assert pedido_tiene_pp6040(None) is False

def test_selector_detecta_pp6040_por_sku():
    p = pedido(item("PP6040H"))
    assert pedido_contiene_pp6040(p) is True


def test_selector_no_detecta_pa9060h_como_pp6040():
    p = pedido(item("PA9060H"))
    assert pedido_contiene_pp6040(p) is False


def test_selector_no_detecta_pp6040_en_descripcion_ni_observaciones():
    p = SimpleNamespace(
        items=[item("PA9060H", descripcion="Producto parecido a PP6040")],
        observaciones="PP6040 mencionado en observaciones",
    )
    assert pedido_contiene_pp6040(p) is False

def test_logistica_defaults_detecta_pp6040_por_sku():
    p = pedido(item("PP6040H"))
    assert pedido_es_plegable_pp6040_service(p) is True


def test_logistica_defaults_no_detecta_pa9060h_como_pp6040():
    p = pedido(item("PA9060H"))
    assert pedido_es_plegable_pp6040_service(p) is False


def test_logistica_defaults_no_detecta_plegable_por_descripcion():
    p = pedido(item("PA9060H", descripcion="Parrilla plegable 90x60"))
    assert pedido_es_plegable_pp6040_service(p) is False

