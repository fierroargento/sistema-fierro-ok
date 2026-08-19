from types import SimpleNamespace

import pytest

from services.inventario_eventos_canal import (
    contrato_desde_pedido,
    contrato_puede_ejecutarse,
    crear_contrato_evento,
    normalizar_cantidades,
)


def test_contrato_normaliza_y_suma_sku_repetidos():
    contrato = crear_contrato_evento(
        canal="Mercado Libre",
        referencia="200001",
        tipo_evento="reservar",
        cantidades={"pp6040h": 2, " PP6040H ": 3},
    )
    assert contrato["cantidades"] == {"PP6040H": 5}
    assert contrato["modo"] == "desconectado"


def test_contrato_rechaza_cantidades_invalidas():
    with pytest.raises(ValueError):
        normalizar_cantidades({"PP6040H": "dos"})
    with pytest.raises(ValueError):
        normalizar_cantidades({"PP6040H": 0})


def test_estados_cancelacion_despacho_y_devolucion_separados():
    pedido = SimpleNamespace(
        canal="Tienda Nube", id_venta="99", ml_pack_id=None,
        tn_order_id="99", id=7,
        items=[SimpleNamespace(sku="A", cantidad=1)],
    )
    assert contrato_desde_pedido(pedido, evento_externo="order/cancelled")["tipo_evento"] == "liberar"
    assert contrato_desde_pedido(pedido, evento_externo="shipped")["tipo_evento"] == "consumir"
    devolucion = contrato_desde_pedido(pedido, evento_externo="returned")
    assert devolucion["tipo_evento"] == "revisar_devolucion"
    assert devolucion["requiere_revision"] is True


def test_despacho_parcial_conserva_solo_cantidades_informadas():
    pedido = SimpleNamespace(
        canal="Mercado Libre", id_venta="55", ml_pack_id=None,
        tn_order_id=None, id=8, items=[],
    )
    contrato = contrato_desde_pedido(
        pedido, evento_externo="shipped", cantidades={"A": 2},
    )
    assert contrato["parcial"] is True
    assert contrato["cantidades"] == {"A": 2}


def test_adaptador_desconectado_nunca_puede_mutar():
    contrato = crear_contrato_evento(
        canal="ml", referencia="1", tipo_evento="reservar", cantidades={"A": 1},
    )
    assert not contrato_puede_ejecutarse(
        contrato, SimpleNamespace(estado="activo"),
    )
