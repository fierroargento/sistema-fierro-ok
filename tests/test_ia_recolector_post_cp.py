from pathlib import Path
from types import SimpleNamespace

from services.ia_recolector_post_cp import (
    ResultadoPostCodigoPostal,
    procesar_post_codigo_postal_recolector,
)


def dependencias_base():
    return {
        "despacho_completo_fn": (
            lambda _pedido: True
        ),
        "actualizar_estado_fn": (
            lambda _pedido: None
        ),
        "db_session": SimpleNamespace(),
        "es_afirmativo_fn": (
            lambda _texto: True
        ),
    }


def test_confirmacion_persistida_finaliza_sin_reenganche():
    pedido = SimpleNamespace(id=10)
    confirmacion = SimpleNamespace(
        confirmada=True
    )
    llamados_auto = []

    resultado = (
        procesar_post_codigo_postal_recolector(
            pedido,
            "opción 1",
            orquestar_confirmacion_fn=(
                lambda *_args, **_kwargs: (
                    SimpleNamespace(
                        confirmacion=confirmacion,
                        persistida=True,
                    )
                )
            ),
            auto_responder_fn=(
                lambda _pedido: (
                    llamados_auto.append(True)
                )
            ),
            **dependencias_base(),
        )
    )

    assert isinstance(
        resultado,
        ResultadoPostCodigoPostal,
    )
    assert resultado.confirmacion is confirmacion
    assert resultado.persistida is True
    assert resultado.finalizar_analisis is True
    assert resultado.reenganche_intentado is False
    assert llamados_auto == []


def test_confirmacion_temprana_recibe_transicion_antes_de_wa():
    pedido = SimpleNamespace(id=1188)
    orden = []

    def orquestar(*_args, **dependencias):
        dependencias["enviar_mensaje_fn"](
            pedido,
            "Continuamos por WhatsApp",
        )
        dependencias["wa_auto_iniciar_fn"](
            pedido,
        )
        return SimpleNamespace(
            confirmacion=SimpleNamespace(confirmada=True),
            persistida=True,
        )

    resultado = procesar_post_codigo_postal_recolector(
        pedido,
        "Perfecto",
        orquestar_confirmacion_fn=orquestar,
        auto_responder_fn=lambda _pedido: None,
        puede_enviar_fn=lambda **_kwargs: (True, "ok"),
        enviar_mensaje_fn=lambda *_args, **_kwargs: orden.append("ml"),
        registrar_envio_fn=lambda **_kwargs: None,
        intentar_cross_sell_fn=lambda *_args, **_kwargs: None,
        wa_auto_iniciar_fn=lambda *_args, **_kwargs: orden.append("wa"),
        **dependencias_base(),
    )

    assert resultado.persistida is True
    assert orden == ["ml", "wa"]


def test_sin_persistencia_reengancha_flujo():
    pedido = SimpleNamespace(id=11)
    confirmacion = SimpleNamespace(
        confirmada=False
    )
    llamados = []

    resultado = (
        procesar_post_codigo_postal_recolector(
            pedido,
            "CP 8504",
            orquestar_confirmacion_fn=(
                lambda *_args, **_kwargs: (
                    SimpleNamespace(
                        confirmacion=confirmacion,
                        persistida=False,
                    )
                )
            ),
            auto_responder_fn=(
                lambda p: (
                    llamados.append(p.id)
                    or (True, "enviada")
                )
            ),
            **dependencias_base(),
        )
    )

    assert resultado.confirmacion is confirmacion
    assert resultado.persistida is False
    assert resultado.finalizar_analisis is False
    assert resultado.reenganche_intentado is True
    assert resultado.reenganche_resultado == (
        True,
        "enviada",
    )
    assert llamados == [11]


def test_error_confirmacion_no_impide_reenganche():
    pedido = SimpleNamespace(id=12)
    logs = []

    def confirmar(*_args, **_kwargs):
        raise RuntimeError("falló confirmación")

    resultado = (
        procesar_post_codigo_postal_recolector(
            pedido,
            "CP 8504",
            orquestar_confirmacion_fn=confirmar,
            auto_responder_fn=(
                lambda _pedido: (False, "sin_datos")
            ),
            logger_fn=logs.append,
            **dependencias_base(),
        )
    )

    assert resultado.reenganche_intentado is True
    assert (
        resultado.error_confirmacion
        == "falló confirmación"
    )
    assert resultado.error_reenganche == ""
    assert len(logs) == 1
    assert "falló confirmación" in logs[0]


def test_error_reenganche_es_tolerado():
    pedido = SimpleNamespace(id=13)
    logs = []

    def reenganchar(_pedido):
        raise RuntimeError("falló reenganche")

    resultado = (
        procesar_post_codigo_postal_recolector(
            pedido,
            "CP 8504",
            orquestar_confirmacion_fn=(
                lambda *_args, **_kwargs: (
                    SimpleNamespace(
                        confirmacion=None,
                        persistida=False,
                    )
                )
            ),
            auto_responder_fn=reenganchar,
            logger_fn=logs.append,
            **dependencias_base(),
        )
    )

    assert resultado.finalizar_analisis is False
    assert resultado.reenganche_intentado is True
    assert (
        resultado.error_reenganche
        == "falló reenganche"
    )
    assert len(logs) == 1
    assert "falló reenganche" in logs[0]


def test_servicio_no_depende_de_app_ni_flask():
    texto = Path(
        "services/ia_recolector_post_cp.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "import app",
        "redirect(",
        "url_for(",
        "db.session",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto
