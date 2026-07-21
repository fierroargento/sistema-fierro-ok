from types import SimpleNamespace

import services.workflow_orquestador_confirmacion_sucursal as workflow


def test_orquestacion_temprana_respeta_orden(
    monkeypatch,
):
    llamadas = []
    confirmacion = SimpleNamespace(confirmada=True)
    plan = SimpleNamespace(confirmada=True)
    persistencia = SimpleNamespace(exitosa=True)

    monkeypatch.setattr(
        workflow,
        "resolver_confirmacion_sucursal_via_cargo_ofrecida",
        lambda *_args, **_kwargs: (
            llamadas.append("resolver")
            or confirmacion
        ),
    )
    monkeypatch.setattr(
        workflow,
        "planificar_post_confirmacion_sucursal",
        lambda **_kwargs: (
            llamadas.append("planificar")
            or plan
        ),
    )
    monkeypatch.setattr(
        workflow,
        "ejecutar_estado_y_persistencia_post_confirmacion",
        lambda **_kwargs: (
            llamadas.append("persistir")
            or persistencia
        ),
    )

    resultado = (
        workflow
        .orquestar_confirmacion_sucursal_temprana(
            SimpleNamespace(id=10),
            "opción 1",
            despacho_completo_fn=lambda _pedido: True,
            actualizar_estado_fn=lambda _pedido: None,
            db_session=SimpleNamespace(),
            log_fn=lambda _mensaje: None,
        )
    )

    assert llamadas == [
        "resolver",
        "planificar",
        "persistir",
    ]
    assert resultado.confirmada is True
    assert resultado.persistida is True
    assert resultado.transicion_ml is None
    assert resultado.finalizacion is None


def test_orquestacion_comun_respeta_orden_completo(
    monkeypatch,
):
    llamadas = []
    confirmacion = SimpleNamespace(confirmada=True)
    plan = SimpleNamespace(
        confirmada=True,
        evaluar_transicion_ml=True,
        mensaje_transicion_ml="Transición",
    )
    transicion = SimpleNamespace(enviada=True)
    persistencia = SimpleNamespace(exitosa=True)
    finalizacion = SimpleNamespace(
        finalizada=True,
        respuesta_flujo={
            "ok": True,
            "estado": "sucursal_confirmada",
        },
    )

    monkeypatch.setattr(
        workflow,
        "resolver_confirmacion_sucursal_via_cargo_ofrecida",
        lambda *_args, **_kwargs: (
            llamadas.append("resolver")
            or confirmacion
        ),
    )
    monkeypatch.setattr(
        workflow,
        "planificar_post_confirmacion_sucursal",
        lambda **_kwargs: (
            llamadas.append("planificar")
            or plan
        ),
    )
    monkeypatch.setattr(
        workflow,
        "ejecutar_transicion_ml_tras_confirmacion_sucursal",
        lambda **_kwargs: (
            llamadas.append("transicion")
            or transicion
        ),
    )
    monkeypatch.setattr(
        workflow,
        "ejecutar_estado_y_persistencia_post_confirmacion",
        lambda **_kwargs: (
            llamadas.append("persistir")
            or persistencia
        ),
    )
    monkeypatch.setattr(
        workflow,
        "finalizar_confirmacion_sucursal_persistida",
        lambda **_kwargs: (
            llamadas.append("finalizar")
            or finalizacion
        ),
    )

    resultado = (
        workflow
        .orquestar_confirmacion_sucursal_comun_ml(
            SimpleNamespace(id=10),
            "opción 1",
            despacho_completo_fn=lambda _pedido: True,
            actualizar_estado_fn=lambda _pedido: None,
            db_session=SimpleNamespace(),
            puede_enviar_fn=lambda **_kwargs: (True, "ok"),
            enviar_mensaje_fn=lambda *_args, **_kwargs: None,
            registrar_envio_fn=lambda **_kwargs: None,
            intentar_cross_sell_fn=lambda *_args, **_kwargs: None,
            wa_auto_iniciar_fn=lambda *_args, **_kwargs: None,
            log_fn=lambda _mensaje: None,
        )
    )

    assert llamadas == [
        "resolver",
        "planificar",
        "transicion",
        "persistir",
        "finalizar",
    ]
    assert resultado.transicion_ml is transicion
    assert resultado.finalizada is True
    assert resultado.respuesta_flujo == {
        "ok": True,
        "estado": "sucursal_confirmada",
    }


def test_orquestacion_comun_omite_transicion_si_plan_no_la_pide(
    monkeypatch,
):
    llamadas = []

    monkeypatch.setattr(
        workflow,
        "resolver_confirmacion_sucursal_via_cargo_ofrecida",
        lambda *_args, **_kwargs: (
            SimpleNamespace(confirmada=True)
        ),
    )
    monkeypatch.setattr(
        workflow,
        "planificar_post_confirmacion_sucursal",
        lambda **_kwargs: SimpleNamespace(
            confirmada=True,
            evaluar_transicion_ml=False,
            mensaje_transicion_ml="",
        ),
    )
    monkeypatch.setattr(
        workflow,
        "ejecutar_transicion_ml_tras_confirmacion_sucursal",
        lambda **_kwargs: llamadas.append("transicion"),
    )
    monkeypatch.setattr(
        workflow,
        "ejecutar_estado_y_persistencia_post_confirmacion",
        lambda **_kwargs: SimpleNamespace(exitosa=True),
    )
    monkeypatch.setattr(
        workflow,
        "finalizar_confirmacion_sucursal_persistida",
        lambda **_kwargs: SimpleNamespace(
            finalizada=True,
            respuesta_flujo={"ok": True},
        ),
    )

    resultado = (
        workflow
        .orquestar_confirmacion_sucursal_comun_ml(
            SimpleNamespace(id=10),
            "opción 1",
            despacho_completo_fn=lambda _pedido: True,
            actualizar_estado_fn=lambda _pedido: None,
            db_session=SimpleNamespace(),
            puede_enviar_fn=lambda **_kwargs: (True, "ok"),
            enviar_mensaje_fn=lambda *_args, **_kwargs: None,
            registrar_envio_fn=lambda **_kwargs: None,
            intentar_cross_sell_fn=lambda *_args, **_kwargs: None,
            wa_auto_iniciar_fn=lambda *_args, **_kwargs: None,
            log_fn=lambda _mensaje: None,
        )
    )

    assert llamadas == []
    assert resultado.transicion_ml is None
    assert resultado.finalizada is True


def test_orquestador_no_importa_app_ni_efectos_concretos():
    from pathlib import Path

    texto = Path(
        "services/"
        "workflow_orquestador_confirmacion_sucursal.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "import app",
        "db.session",
        "ml_enviar_mensaje",
        "registrar_envio_automatico",
        "wa_auto_iniciar_desde_ml",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto
