from types import SimpleNamespace

from services.inventario_pedidos import (
    automatizacion_puede_mutar,
    agrupar_items_pedido,
    clave_evento_pedido,
    clasificar_evento_pedido,
    evaluar_preparacion_automatizacion,
)


def test_clasifica_eventos_sin_ejecutar_movimientos():
    assert clasificar_evento_pedido("cancelado") == "liberar"
    assert clasificar_evento_pedido("despachado") == "consumir"
    assert clasificar_evento_pedido("nuevo") == "reservar"


def test_clave_idempotente_aisla_organizacion_pedido_y_evento():
    assert clave_evento_pedido(8, 1204, "reserva") == "org:8:pedido:1204:reserva"
    assert clave_evento_pedido(9, 1204, "reserva") != clave_evento_pedido(8, 1204, "reserva")


def test_agrupa_sku_repetidos_del_pedido():
    items = [SimpleNamespace(sku="PP6040H", cantidad=2), SimpleNamespace(sku="PP6040H", cantidad=3)]
    assert agrupar_items_pedido(items) == {"PP6040H": 5}


def test_activacion_exige_conteo_conciliado_y_stock_no_negativo():
    sucursal = SimpleNamespace(id=4, activa=True)
    configuracion = SimpleNamespace(permitir_stock_negativo=False)
    existencia = SimpleNamespace(control_activo=True, actual=0, item_inventario=object())
    errores = evaluar_preparacion_automatizacion(configuracion, sucursal=sucursal, existencias=[existencia], conteos=[])
    assert any("inventario físico inicial" in error for error in errores)
    conteo = SimpleNamespace(estado="conciliado")
    assert evaluar_preparacion_automatizacion(configuracion, sucursal=sucursal, existencias=[existencia], conteos=[conteo]) == []
    configuracion.permitir_stock_negativo = True
    assert any("stock negativo" in error for error in evaluar_preparacion_automatizacion(configuracion, sucursal=sucursal, existencias=[existencia], conteos=[conteo]))


def test_solo_estado_activo_autoriza_mutaciones():
    assert not automatizacion_puede_mutar(None)
    assert not automatizacion_puede_mutar(SimpleNamespace(estado="validacion"))
    assert automatizacion_puede_mutar(SimpleNamespace(estado="activo"))
