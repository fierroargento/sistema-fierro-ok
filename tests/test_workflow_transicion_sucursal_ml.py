from pathlib import Path
from types import SimpleNamespace

from services.workflow_transicion_sucursal_ml import (
    ejecutar_transicion_ml_tras_confirmacion_sucursal,
)


def pedido_fake():
    return SimpleNamespace(id=25)


def test_transicion_permitida_envia_y_registra_en_orden():
    llamadas = []
    pedido = pedido_fake()

    def puede_enviar(**kwargs):
        llamadas.append(("puede", kwargs))
        return True, "permitido"

    def enviar(*args, **kwargs):
        llamadas.append(("enviar", args, kwargs))

    def registrar(**kwargs):
        llamadas.append(("registrar", kwargs))

    resultado = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=pedido,
            texto="Transición a WhatsApp",
            puede_enviar_fn=puede_enviar,
            enviar_mensaje_fn=enviar,
            registrar_envio_fn=registrar,
            log_fn=lambda _mensaje: None,
        )
    )

    assert resultado.enviada is True
    assert resultado.estado == "enviada"
    assert [
        llamada[0]
        for llamada in llamadas
    ] == [
        "puede",
        "enviar",
        "registrar",
    ]

    assert llamadas[0][1] == {
        "pedido": pedido,
        "canal": "ml",
        "texto": "Transición a WhatsApp",
    }
    assert llamadas[1][1] == (
        pedido,
        "Transición a WhatsApp",
    )
    assert llamadas[1][2] == {
        "permitir_requiere_operador": True,
    }
    assert llamadas[2][1] == {
        "pedido": pedido,
        "canal": "ml",
        "texto": "Transición a WhatsApp",
    }


def test_transicion_bloqueada_no_envia_ni_registra():
    llamadas = []
    logs = []

    resultado = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=pedido_fake(),
            texto="Mensaje",
            puede_enviar_fn=(
                lambda **_kwargs: (
                    False,
                    "whatsapp_activo",
                )
            ),
            enviar_mensaje_fn=lambda *_args, **_kwargs: (
                llamadas.append("enviar")
            ),
            registrar_envio_fn=lambda **_kwargs: (
                llamadas.append("registrar")
            ),
            log_fn=logs.append,
        )
    )

    assert resultado.omitida is True
    assert resultado.motivo == "whatsapp_activo"
    assert llamadas == []
    assert len(logs) == 1
    assert "ML transicion WA omitida" in logs[0]
    assert "whatsapp_activo" in logs[0]


def test_error_de_envio_no_registra_y_devuelve_error():
    llamadas = []
    logs = []

    def enviar_error(*_args, **_kwargs):
        llamadas.append("enviar")
        raise RuntimeError("fallo ml")

    resultado = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=pedido_fake(),
            texto="Mensaje",
            puede_enviar_fn=(
                lambda **_kwargs: (True, "ok")
            ),
            enviar_mensaje_fn=enviar_error,
            registrar_envio_fn=lambda **_kwargs: (
                llamadas.append("registrar")
            ),
            log_fn=logs.append,
        )
    )

    assert resultado.estado == "error"
    assert resultado.motivo == "fallo ml"
    assert llamadas == ["enviar"]
    assert len(logs) == 1
    assert "No se pudo enviar" in logs[0]


def test_error_al_registrar_devuelve_error():
    llamadas = []

    def registrar_error(**_kwargs):
        llamadas.append("registrar")
        raise RuntimeError("fallo registro")

    resultado = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=pedido_fake(),
            texto="Mensaje",
            puede_enviar_fn=(
                lambda **_kwargs: (True, "ok")
            ),
            enviar_mensaje_fn=(
                lambda *_args, **_kwargs: (
                    llamadas.append("enviar")
                )
            ),
            registrar_envio_fn=registrar_error,
            log_fn=lambda _mensaje: None,
        )
    )

    assert resultado.estado == "error"
    assert resultado.motivo == "fallo registro"
    assert llamadas == [
        "enviar",
        "registrar",
    ]


def test_sin_pedido_o_texto_no_invoca_dependencias():
    llamadas = []

    dependencias = {
        "puede_enviar_fn": (
            lambda **_kwargs: llamadas.append("puede")
        ),
        "enviar_mensaje_fn": (
            lambda *_args, **_kwargs: (
                llamadas.append("enviar")
            )
        ),
        "registrar_envio_fn": (
            lambda **_kwargs: llamadas.append("registrar")
        ),
    }

    sin_pedido = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=None,
            texto="Mensaje",
            **dependencias,
        )
    )
    sin_texto = (
        ejecutar_transicion_ml_tras_confirmacion_sucursal(
            pedido=pedido_fake(),
            texto="",
            **dependencias,
        )
    )

    assert sin_pedido.estado == "no_aplica"
    assert sin_pedido.motivo == "sin_pedido"
    assert sin_texto.estado == "no_aplica"
    assert sin_texto.motivo == "sin_texto"
    assert llamadas == []


def test_servicio_no_persiste_ni_decide_cross_sell():
    texto = Path(
        "services/workflow_transicion_sucursal_ml.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "from app import",
        "db.session",
        "actualizar_estado_automatico",
        "intentar_wa_cross_sell",
    ]

    for prohibido in prohibidos:
        assert prohibido not in texto
