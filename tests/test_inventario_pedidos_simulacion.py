from types import SimpleNamespace

from services.inventario_pedidos import (
    construir_vista_previa_evento,
    resolver_vinculo_pedido,
)


def _pedido(**cambios):
    base = {
        "id": 1204,
        "canal": "Mercado Libre",
        "ml_cuenta_id": 7,
        "tn_order_id": None,
        "tn_cuenta_id": None,
        "items": [SimpleNamespace(sku="PP6040H", cantidad=2)],
    }
    base.update(cambios)
    return SimpleNamespace(**base)


def _vinculo(**cambios):
    base = {
        "organizacion_id": 3,
        "mercado_libre_cuenta_id": 7,
        "sucursal_operativa_id": 5,
        "tienda_nube_cuenta_id": None,
        "estado": "activo",
    }
    base.update(cambios)
    return SimpleNamespace(**base)


def test_resuelve_ml_por_cuenta_empresarial_exacta():
    vinculo, error = resolver_vinculo_pedido(_pedido(), [_vinculo()])
    assert error is None
    assert vinculo.organizacion_id == 3


def test_tienda_nube_se_bloquea_hasta_persistir_cuenta_origen():
    vinculo, error = resolver_vinculo_pedido(
        _pedido(canal="Tienda Nube", ml_cuenta_id=None, tn_order_id="99"),
        [_vinculo()],
    )
    assert vinculo is None
    assert "cuenta de origen" in error


def test_resuelve_tienda_nube_por_cuenta_empresarial_exacta():
    pedido = _pedido(
        canal="Tienda Nube", ml_cuenta_id=None, tn_order_id="99", tn_cuenta_id=12,
    )
    vinculo = _vinculo(
        mercado_libre_cuenta_id=None, tienda_nube_cuenta_id=12,
    )
    resuelto, error = resolver_vinculo_pedido(pedido, [vinculo])
    assert error is None
    assert resuelto.organizacion_id == 3


def test_pedido_no_resuelto_no_expone_sku_ni_lineas():
    vista = construir_vista_previa_evento(
        _pedido(ml_cuenta_id=999),
        "reservar",
        configuracion=None,
        vinculos=[_vinculo()],
        items_inventario=[],
        existencias=[],
    )
    assert vista["organizacion_id"] == 0
    assert vista["pedido_id"] == 0
    assert vista["lineas"] == []


def test_simulacion_detecta_stock_insuficiente_sin_mutarlo():
    item = SimpleNamespace(id=11, organizacion_id=3, sku="PP6040H", activo=True)
    existencia = SimpleNamespace(
        item_inventario_id=11,
        organizacion_id=3,
        sucursal_operativa_id=5,
        control_activo=True,
        stock_actual=1,
        stock_reservado=0,
        stock_bloqueado=0,
    )
    configuracion = SimpleNamespace(estado="activo", sucursal_operativa_id=5)
    vista = construir_vista_previa_evento(
        _pedido(),
        "reservar",
        configuracion=configuracion,
        vinculos=[_vinculo()],
        items_inventario=[item],
        existencias=[existencia],
    )
    assert vista["resultado"] == "bloqueado"
    assert "Stock disponible insuficiente" in vista["lineas"][0]["errores"]
    assert existencia.stock_actual == 1
    assert existencia.stock_reservado == 0


def test_simulacion_lista_no_genera_efectos_reales():
    item = SimpleNamespace(id=11, organizacion_id=3, sku="PP6040H", activo=True)
    existencia = SimpleNamespace(
        item_inventario_id=11,
        organizacion_id=3,
        sucursal_operativa_id=5,
        control_activo=True,
        stock_actual=10,
        stock_reservado=0,
        stock_bloqueado=0,
    )
    vista = construir_vista_previa_evento(
        _pedido(), "reservar",
        configuracion=SimpleNamespace(estado="activo", sucursal_operativa_id=5),
        vinculos=[_vinculo()], items_inventario=[item], existencias=[existencia],
    )
    assert vista["resultado"] == "listo"
    assert vista["modo"] == "simulacion"
    assert existencia.stock_actual == 10
