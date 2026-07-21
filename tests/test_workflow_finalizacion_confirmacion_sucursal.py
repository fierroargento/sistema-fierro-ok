from pathlib import Path
from types import SimpleNamespace

from services.workflow_finalizacion_confirmacion_sucursal import (
    finalizar_confirmacion_sucursal_persistida,
)


def plan_fake(**cambios):
    datos = {
        "confirmada": True,
        "intentar_cross_sell": True,
        "motivo_cross_sell": (
            "sucursal_confirmada_sin_auto_respuesta"
        ),
    }
    datos.update(cambios)
    return SimpleNamespace(**datos)


def persistencia_fake(exitosa=True):
    return SimpleNamespace(exitosa=exitosa)


def test_persistencia_fallida_no_finaliza_ni_hace_cross_sell():
    llamadas = []

    resultado = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(),
            resultado_persistencia=(
                persistencia_fake(False)
            ),
            intentar_cross_sell_fn=(
                lambda *_args, **_kwargs: (
                    llamadas.append("cross")
                )
            ),
            wa_auto_iniciar_fn=lambda *_args: None,
            db_session=object(),
        )
    )

    assert resultado.finalizada is False
    assert resultado.estado == "no_finalizada"
    assert resultado.motivo == "persistencia_no_exitosa"
    assert resultado.respuesta_flujo is None
    assert llamadas == []


def test_plan_sin_cross_sell_finaliza_directamente():
    resultado = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(
                intentar_cross_sell=False,
            ),
            resultado_persistencia=(
                persistencia_fake()
            ),
            intentar_cross_sell_fn=(
                lambda *_args, **_kwargs: None
            ),
            wa_auto_iniciar_fn=lambda *_args: None,
            db_session=object(),
        )
    )

    assert resultado.finalizada is True
    assert resultado.cross_sell_intentado is False
    assert resultado.respuesta_flujo == {
        "ok": True,
        "estado": "sucursal_confirmada",
        "sucursal_confirmada": True,
    }


def test_cross_sell_recibe_dependencias_y_motivo():
    llamadas = []
    pedido = SimpleNamespace(id=10)
    sesion = object()

    def wa_auto(*_args):
        return True, "ok"

    def cross(*args, **kwargs):
        llamadas.append((args, kwargs))
        return {"ok": True}

    resultado = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=pedido,
            plan=plan_fake(),
            resultado_persistencia=(
                persistencia_fake()
            ),
            intentar_cross_sell_fn=cross,
            wa_auto_iniciar_fn=wa_auto,
            db_session=sesion,
        )
    )

    assert resultado.finalizada is True
    assert resultado.cross_sell_intentado is True
    assert resultado.cross_sell_resultado == {
        "ok": True,
    }
    assert len(llamadas) == 1
    assert llamadas[0][0] == (pedido,)
    assert llamadas[0][1] == {
        "wa_auto_iniciar_desde_ml_fn": wa_auto,
        "db_session": sesion,
        "motivo": (
            "sucursal_confirmada_sin_auto_respuesta"
        ),
    }


def test_error_cross_sell_no_invalida_confirmacion():
    logs = []

    def cross_error(*_args, **_kwargs):
        raise RuntimeError("fallo cross")

    resultado = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(),
            resultado_persistencia=(
                persistencia_fake()
            ),
            intentar_cross_sell_fn=cross_error,
            wa_auto_iniciar_fn=lambda *_args: None,
            db_session=object(),
            log_fn=logs.append,
        )
    )

    assert resultado.finalizada is True
    assert resultado.cross_sell_intentado is True
    assert resultado.motivo == "fallo cross"
    assert resultado.respuesta_flujo == {
        "ok": True,
        "estado": "sucursal_confirmada",
        "sucursal_confirmada": True,
    }
    assert len(logs) == 1
    assert "No se pudo iniciar WA" in logs[0]


def test_sin_confirmacion_no_finaliza():
    resultado = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(confirmada=False),
            resultado_persistencia=(
                persistencia_fake()
            ),
            intentar_cross_sell_fn=(
                lambda *_args, **_kwargs: None
            ),
            wa_auto_iniciar_fn=lambda *_args: None,
            db_session=object(),
        )
    )

    assert resultado.estado == "no_aplica"
    assert resultado.finalizada is False
    assert resultado.respuesta_flujo is None


def test_respuesta_flujo_devuelve_diccionario_nuevo():
    resultado = (
        finalizar_confirmacion_sucursal_persistida(
            pedido=SimpleNamespace(id=10),
            plan=plan_fake(
                intentar_cross_sell=False,
            ),
            resultado_persistencia=(
                persistencia_fake()
            ),
            intentar_cross_sell_fn=(
                lambda *_args, **_kwargs: None
            ),
            wa_auto_iniciar_fn=lambda *_args: None,
            db_session=object(),
        )
    )

    primera = resultado.respuesta_flujo
    segunda = resultado.respuesta_flujo

    assert primera == segunda
    assert primera is not segunda


def test_servicio_no_persiste_ni_envia_mensajes():
    texto = Path(
        "services/"
        "workflow_finalizacion_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "db.session.commit",
        "db.session.rollback",
        "ml_enviar",
        "wa_enviar",
        "actualizar_estado_automatico",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto
