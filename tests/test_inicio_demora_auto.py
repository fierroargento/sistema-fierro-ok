from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from domain.estados import Estado
from services.inicio_demoras import actualizar_demoras_inicio_pedidos_service


def _debe_pasar_a_demora_fake(pedido):
    return (
        getattr(pedido, "estado", None) == Estado.DESPACHADO
        and getattr(pedido, "fecha_despachado", None)
        and datetime.now(UTC) - pedido.fecha_despachado >= timedelta(hours=72)
    )


def test_inicio_marca_demora_para_pedido_despachado_vencido():
    pedido = SimpleNamespace(
        id=1,
        estado=Estado.DESPACHADO,
        fecha_despachado=datetime.now(UTC) - timedelta(hours=100),
    )

    cambios = actualizar_demoras_inicio_pedidos_service(
        [pedido],
        debe_pasar_a_demora_fn=_debe_pasar_a_demora_fake,
        estado_demora=Estado.DEMORA,
        commit=False,
    )

    assert cambios == 1
    assert pedido.estado == Estado.DEMORA


def test_inicio_no_marca_demora_si_pedido_no_esta_despachado():
    pedido = SimpleNamespace(
        id=2,
        estado=Estado.VERIFICAR_DESTINO,
        fecha_despachado=datetime.now(UTC) - timedelta(hours=100),
    )

    cambios = actualizar_demoras_inicio_pedidos_service(
        [pedido],
        debe_pasar_a_demora_fn=_debe_pasar_a_demora_fake,
        estado_demora=Estado.DEMORA,
        commit=False,
    )

    assert cambios == 0
    assert pedido.estado == Estado.VERIFICAR_DESTINO


def test_inicio_no_marca_demora_si_despacho_es_reciente():
    pedido = SimpleNamespace(
        id=3,
        estado=Estado.DESPACHADO,
        fecha_despachado=datetime.now(UTC) - timedelta(hours=2),
    )

    cambios = actualizar_demoras_inicio_pedidos_service(
        [pedido],
        debe_pasar_a_demora_fn=_debe_pasar_a_demora_fake,
        estado_demora=Estado.DEMORA,
        commit=False,
    )

    assert cambios == 0
    assert pedido.estado == Estado.DESPACHADO
