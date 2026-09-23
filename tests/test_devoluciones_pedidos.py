from types import SimpleNamespace

import pytest

from services.devoluciones_pedidos import (
    validar_cierre_reclamo_ml,
    validar_devolucion_pedido,
)


def _pedido(**cambios):
    base = dict(
        organizacion_id=7, unidad_negocio_id=9, estado="No entregado",
        canal="Mercado Libre",
        items=[SimpleNamespace(id=1, sku="SKU-1", cantidad=2)],
    )
    base.update(cambios)
    return SimpleNamespace(**base)


def _datos_devolucion(**cambios):
    base = {
        "fecha_devolucion": "2026-09-23T10:30",
        "estado_devolucion": "parcial",
        "observacion_devolucion": "Recepción interna",
        "estado_item_1": "parcial",
        "cantidad_ok_1": "1",
        "cantidad_danada_1": "1",
        "obs_item_1": "Una unidad dañada",
    }
    base.update(cambios)
    return base


def test_devolucion_valida_todo_antes_de_mutar():
    fecha, estado, observacion, items = validar_devolucion_pedido(
        _pedido(), _datos_devolucion(), organizacion_id=7, unidad_negocio_id=9
    )
    assert fecha.year == 2026 and estado == "parcial"
    assert observacion == "Recepción interna"
    assert items[0].cantidad_ok == items[0].cantidad_danada == 1


@pytest.mark.parametrize("cambio", [
    {"estado_devolucion": "inventado"},
    {"estado_item_1": "inventado"},
    {"cantidad_ok_1": "nan"},
    {"cantidad_ok_1": "2", "cantidad_danada_1": "1"},
])
def test_devolucion_rechaza_datos_fuera_de_contrato(cambio):
    with pytest.raises(ValueError):
        validar_devolucion_pedido(
            _pedido(), _datos_devolucion(**cambio),
            organizacion_id=7, unidad_negocio_id=9,
        )


def test_devolucion_rechaza_otro_tenant():
    with pytest.raises(ValueError, match="organización activa"):
        validar_devolucion_pedido(
            _pedido(), _datos_devolucion(), organizacion_id=8, unidad_negocio_id=9
        )


def test_cierre_reclamo_rechaza_nan_y_resultado_inventado():
    pedido = _pedido(estado="Reclamar a Mercado Libre")
    base = {
        "numero_reclamo_ml": "ML-1", "resultado_reclamo_ml": "parcial",
        "monto_recuperado_ml": "1000,50", "observacion_reclamo_ml": "",
    }
    assert validar_cierre_reclamo_ml(
        pedido, base, organizacion_id=7, unidad_negocio_id=9
    )[2] == 1000.5
    for cambio in ({"monto_recuperado_ml": "nan"}, {"resultado_reclamo_ml": "otro"}):
        with pytest.raises(ValueError):
            validar_cierre_reclamo_ml(
                pedido, {**base, **cambio}, organizacion_id=7, unidad_negocio_id=9
            )
