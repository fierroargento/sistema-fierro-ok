from types import SimpleNamespace

from services.ia_recolector_workflow import (
    procesar_resultado_recolector,
)


def dependencias(**cambios):
    valores = {
        "parece_nickname_fn": (
            lambda _cliente, _nickname: False
        ),
        "es_ml_acordas_entrega_fn": (
            lambda _pedido: False
        ),
        "pedido_es_plegable_pp6040_fn": (
            lambda _pedido: False
        ),
    }
    valores.update(cambios)
    return valores


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
        **dependencias(),
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
        **dependencias(),
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
        **dependencias(),
    )

    assert resultado.handoff_intentado is True
    assert resultado.handoff_ok is False
    assert (
        resultado.motivo_handoff
        == "ml_sigue_recolectando"
    )


def test_propaga_dependencias_operativas_al_aplicador():
    marcadores = {
        "nickname": object(),
        "acordas": object(),
        "plegable": object(),
    }
    recibidas = {}

    def aplicar(*_args, **kwargs):
        recibidas.update(kwargs)
        return aplicacion_fake()

    procesar_resultado_recolector(
        SimpleNamespace(id=13),
        "mensaje",
        {"ok": True},
        parece_nickname_fn=marcadores["nickname"],
        es_ml_acordas_entrega_fn=marcadores["acordas"],
        pedido_es_plegable_pp6040_fn=(
            marcadores["plegable"]
        ),
        iniciar_handoff_fn=(
            lambda *_args, **_kwargs: (
                True,
                "no_usado",
            )
        ),
        aplicar_resultado_fn=aplicar,
    )

    assert (
        recibidas["parece_nickname_fn"]
        is marcadores["nickname"]
    )
    assert (
        recibidas["es_ml_acordas_entrega_fn"]
        is marcadores["acordas"]
    )
    assert (
        recibidas[
            "pedido_es_plegable_pp6040_fn"
        ]
        is marcadores["plegable"]
    )


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
        **dependencias(),
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
