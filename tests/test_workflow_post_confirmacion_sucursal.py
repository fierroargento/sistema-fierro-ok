from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from services.workflow_post_confirmacion_sucursal import (
    FLUJO_CONFIRMACION_COMUN_ML,
    FLUJO_CONFIRMACION_TEMPRANA,
    MOTIVO_CROSS_SELL_TRAS_SUCURSAL,
    construir_mensaje_transicion_sucursal_ml,
    planificar_post_confirmacion_sucursal,
)
from services.workflow_confirmacion_sucursal import (
    ResultadoConfirmacionSucursal,
)


def pedido_fake(**cambios):
    datos = {
        "cliente": "Martín Fierro",
        "sucursal_nombre": "Terminal Viedma",
        "direccion": "Ruta 3",
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def resultado_confirmado():
    return ResultadoConfirmacionSucursal(
        estado="confirmada",
        motivo="sucursal_confirmada_por_texto",
    )


def test_sin_confirmacion_no_planifica_acciones():
    plan = planificar_post_confirmacion_sucursal(
        resultado_confirmacion=(
            ResultadoConfirmacionSucursal(
                estado="sin_confirmacion",
                motivo="sin_eleccion_explicita",
            )
        ),
        pedido=pedido_fake(),
        flujo=FLUJO_CONFIRMACION_COMUN_ML,
    )

    assert plan.confirmada is False
    assert plan.actualizar_estado is False
    assert plan.persistir is False
    assert plan.detener_flujo is False
    assert plan.evaluar_transicion_ml is False
    assert plan.intentar_cross_sell is False
    assert plan.mensaje_transicion_ml == ""
    assert plan.motivo_cross_sell == ""


def test_confirmacion_temprana_no_reenvia_ni_hace_cross_sell():
    plan = planificar_post_confirmacion_sucursal(
        resultado_confirmacion=resultado_confirmado(),
        pedido=pedido_fake(),
        flujo=FLUJO_CONFIRMACION_TEMPRANA,
    )

    assert plan.confirmada is True
    assert plan.actualizar_estado is True
    assert plan.persistir is True
    assert plan.detener_flujo is True
    assert plan.evaluar_transicion_ml is False
    assert plan.intentar_cross_sell is False
    assert plan.mensaje_transicion_ml == ""
    assert plan.motivo_cross_sell == ""


def test_flujo_comun_ml_planifica_transicion_y_cross_sell():
    plan = planificar_post_confirmacion_sucursal(
        resultado_confirmacion=resultado_confirmado(),
        pedido=pedido_fake(),
        flujo=FLUJO_CONFIRMACION_COMUN_ML,
    )

    assert plan.confirmada is True
    assert plan.actualizar_estado is True
    assert plan.persistir is True
    assert plan.detener_flujo is True
    assert plan.evaluar_transicion_ml is True
    assert plan.intentar_cross_sell is True
    assert (
        plan.motivo_cross_sell
        == MOTIVO_CROSS_SELL_TRAS_SUCURSAL
    )
    assert "Perfecto Martín" in plan.mensaje_transicion_ml
    assert (
        "Sucursal: Terminal Viedma"
        in plan.mensaje_transicion_ml
    )
    assert (
        "Direccion: Ruta 3"
        in plan.mensaje_transicion_ml
    )
    assert "WhatsApp" in plan.mensaje_transicion_ml


def test_mensaje_usa_cliente_generico_si_falta_nombre():
    mensaje = construir_mensaje_transicion_sucursal_ml(
        pedido_fake(cliente=""),
    )

    assert mensaje.startswith("Perfecto Cliente")


def test_flujo_invalido_falla_explicito():
    with pytest.raises(
        ValueError,
        match="flujo_post_confirmacion_invalido",
    ):
        planificar_post_confirmacion_sucursal(
            resultado_confirmacion=resultado_confirmado(),
            pedido=pedido_fake(),
            flujo="otro",
        )


def test_plan_es_inmutable():
    plan = planificar_post_confirmacion_sucursal(
        resultado_confirmacion=resultado_confirmado(),
        pedido=pedido_fake(),
        flujo=FLUJO_CONFIRMACION_TEMPRANA,
    )

    with pytest.raises(FrozenInstanceError):
        plan.persistir = False


def test_servicio_no_ejecuta_efectos_externos():
    from pathlib import Path

    texto = Path(
        "services/"
        "workflow_post_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "db.session",
        "ml_enviar_mensaje",
        "registrar_envio_automatico",
        "intentar_wa_cross_sell",
        "actualizar_estado_automatico(",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto
