from types import SimpleNamespace

from services.ia_recolector_workflow import (
    procesar_resultado_recolector,
)


def aplicacion_fake(
    *,
    iniciar_handoff=False,
    faltantes=(),
):
    return SimpleNamespace(
        iniciar_handoff=iniciar_handoff,
        faltantes=tuple(faltantes),
    )


def test_aplica_resultado_sin_handoff_si_no_corresponde():
    pedido = SimpleNamespace(id=10)
    llamadas = []

    def aplicar(
        pedido_recibido,
        texto_recibido,
        resultado_recibido,
        **dependencias_recibidas,
    ):
        llamadas.append(
            (
                pedido_recibido,
                texto_recibido,
                resultado_recibido,
                dependencias_recibidas,
            )
        )
        return aplicacion_fake()

    def handoff(*_args, **_kwargs):
        raise AssertionError(
            "no debe iniciar handoff"
        )

    resultado = procesar_resultado_recolector(
        pedido,
        "mensaje",
        {"ok": True},
        iniciar_handoff_fn=handoff,
        aplicar_resultado_fn=aplicar,
    )

    assert len(llamadas) == 1
    assert llamadas[0][0] is pedido
    assert llamadas[0][1] == "mensaje"
    assert llamadas[0][2] == {"ok": True}
    assert resultado.handoff_intentado is False
    assert resultado.handoff_ok is None
    assert resultado.motivo_handoff == "no_requerido"


def test_inicia_handoff_con_faltantes_y_motivo():
    pedido = SimpleNamespace(id=11)
    llamadas = []

    def aplicar(*_args, **_kwargs):
        return aplicacion_fake(
            iniciar_handoff=True,
            faltantes=("dni", "telefono"),
        )

    def handoff(
        pedido_recibido,
        *,
        faltantes,
        motivo,
    ):
        llamadas.append(
            (
                pedido_recibido,
                faltantes,
                motivo,
            )
        )
        return True, "wa_iniciado"

    resultado = procesar_resultado_recolector(
        pedido,
        "datos",
        {"ok": True},
        iniciar_handoff_fn=handoff,
        motivo_handoff="recolector_prueba",
        aplicar_resultado_fn=aplicar,
    )

    assert llamadas == [
        (
            pedido,
            ["dni", "telefono"],
            "recolector_prueba",
        )
    ]
    assert resultado.handoff_intentado is True
    assert resultado.handoff_ok is True
    assert resultado.motivo_handoff == "wa_iniciado"


def test_conserva_resultado_de_handoff_bloqueado():
    def aplicar(*_args, **_kwargs):
        return aplicacion_fake(
            iniciar_handoff=True,
            faltantes=("direccion",),
        )

    resultado = procesar_resultado_recolector(
        SimpleNamespace(id=12),
        "mensaje",
        {"ok": True},
        iniciar_handoff_fn=(
            lambda *_args, **_kwargs: (
                False,
                "ml_sigue_recolectando",
            )
        ),
        aplicar_resultado_fn=aplicar,
    )

    assert resultado.handoff_intentado is True
    assert resultado.handoff_ok is False
    assert (
        resultado.motivo_handoff
        == "ml_sigue_recolectando"
    )


def test_workflow_usa_reglas_canonicas_sin_inyeccion():
    from pathlib import Path

    servicio = Path(
        "services/ia_recolector_workflow.py"
    ).read_text(encoding="utf-8")

    assert (
        "from modules.bot_ml.billing import ("
        in servicio
    )
    assert (
        "from services.logistica_defaults import ("
        in servicio
    )
    assert "parece_nickname_fn=parece_nickname_ml" in servicio
    assert (
        "es_ml_acordas_entrega_service"
        in servicio
    )
    assert (
        "pedido_es_plegable_pp6040_service"
        in servicio
    )

    parametros_retirados = [
        "parece_nickname_fn: Callable",
        "es_ml_acordas_entrega_fn: Callable",
        "pedido_es_plegable_pp6040_fn: Callable",
    ]

    for parametro in parametros_retirados:
        assert parametro not in servicio


def test_resultado_del_flujo_es_inmutable():
    resultado = procesar_resultado_recolector(
        SimpleNamespace(id=14),
        "mensaje",
        {"ok": True},
        iniciar_handoff_fn=(
            lambda *_args, **_kwargs: (
                True,
                "no_usado",
            )
        ),
        aplicar_resultado_fn=(
            lambda *_args, **_kwargs: (
                aplicacion_fake()
            )
        ),
    )

    try:
        resultado.handoff_ok = True
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "el resultado debe ser inmutable"
        )


def test_servicio_no_importa_app_ni_persiste():
    from pathlib import Path

    texto = Path(
        "services/ia_recolector_workflow.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "import app",
        "db.session",
        "commit(",
        "rollback(",
        "ml_enviar_mensaje",
        "cross_sell",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto


def test_sin_ejecutor_no_intenta_handoff_aunque_aplicador_lo_solicite():
    resultado = procesar_resultado_recolector(
        SimpleNamespace(id=15),
        "mensaje recibido por WhatsApp",
        {"ok": True},
        aplicar_resultado_fn=(
            lambda *_args, **_kwargs: (
                aplicacion_fake(
                    iniciar_handoff=True,
                    faltantes=("dni",),
                )
            )
        ),
    )

    assert resultado.handoff_intentado is False
    assert resultado.handoff_ok is None
    assert resultado.motivo_handoff == "sin_ejecutor"
    assert resultado.aplicacion.faltantes == (
        "dni",
    )
