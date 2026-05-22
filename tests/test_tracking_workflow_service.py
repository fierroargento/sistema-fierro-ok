from types import SimpleNamespace

from domain.estados import Estado
from services.tracking_workflow import (
    aplicar_estado_tracking_seguro_service,
)


def pedido_base(**overrides):
    datos = {
        "estado": Estado.DESPACHADO,
        "canal": "",
        "ml_tipo": "",
        "ia_resumen": "",
        "fecha_entregado": None,
    }
    datos.update(overrides)
    return SimpleNamespace(**datos)


def test_tracking_entregado_pasa_a_entregado():
    pedido = pedido_base()

    resultado = aplicar_estado_tracking_seguro_service(
        pedido,
        "entregado",
    )

    assert resultado == Estado.ENTREGADO
    assert pedido.estado == Estado.ENTREGADO
    assert pedido.fecha_entregado is not None


def test_tracking_entregado_ml_acordas_pasa_a_verificar_destino():
    pedido = pedido_base(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
    )

    resultado = aplicar_estado_tracking_seguro_service(
        pedido,
        "entregado",
    )

    assert resultado == Estado.VERIFICAR_DESTINO
    assert pedido.estado == Estado.VERIFICAR_DESTINO
    assert "TRACKING:" in pedido.ia_resumen


def test_tracking_sucursal_pasa_a_verificar_destino():
    pedido = pedido_base()

    resultado = aplicar_estado_tracking_seguro_service(
        pedido,
        "sucursal",
    )

    assert resultado == Estado.VERIFICAR_DESTINO
    assert pedido.estado == Estado.VERIFICAR_DESTINO


def test_tracking_no_toca_estados_cerrados():
    pedido = pedido_base(
        estado=Estado.FINALIZADO,
    )

    resultado = aplicar_estado_tracking_seguro_service(
        pedido,
        "entregado",
    )

    assert resultado is None
    assert pedido.estado == Estado.FINALIZADO


def test_tracking_ml_acordas_no_avanza_desde_estado_invalido():
    pedido = pedido_base(
        estado=Estado.EMBALADO,
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
    )

    resultado = aplicar_estado_tracking_seguro_service(
        pedido,
        "entregado",
    )

    assert resultado is None
    assert pedido.estado == Estado.EMBALADO