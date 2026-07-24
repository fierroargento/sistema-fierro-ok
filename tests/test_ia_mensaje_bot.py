from datetime import datetime
from pathlib import Path

from modules.whatsapp import runtime
from services.ia_mensajes import (
    ia_hash_texto_service,
    ia_marcar_mensaje_bot_service,
    ia_marcar_respuesta_cliente_service,
)


class SessionFake:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class PedidoFake:
    id = 123
    ia_esperando_respuesta = False
    ia_ultimo_mensaje_bot = None
    ia_canal_activo = None
    ia_respuesta_enviada_hash = None
    ia_ultima_respuesta_enviada = None


def test_servicio_marca_mensaje_bot_y_audita():
    pedido = PedidoFake()
    session = SessionFake()
    fecha = datetime(2026, 7, 24, 12, 0, 0)
    estados = []
    eventos = []

    resultado = ia_marcar_mensaje_bot_service(
        pedido,
        " whatsapp ",
        lambda *args, **kwargs: estados.append(
            (args, kwargs)
        ),
        lambda **kwargs: eventos.append(kwargs),
        session,
        texto="Hola",
        ahora_fn=lambda: fecha,
    )

    assert resultado is True
    assert pedido.ia_esperando_respuesta is True
    assert pedido.ia_ultimo_mensaje_bot == fecha
    assert pedido.ia_canal_activo == "whatsapp"
    assert pedido.ia_respuesta_enviada_hash == (
        ia_hash_texto_service("Hola")
    )
    assert pedido.ia_ultima_respuesta_enviada == fecha
    assert session.commits == 1
    assert session.rollbacks == 0

    assert estados[0][0] == (pedido,)
    assert estados[0][1] == {
        "owner_actual": "bot",
        "canal_activo": "whatsapp",
        "estado_conversacional": (
            "esperando_respuesta"
        ),
        "takeover_activo": False,
        "bot_pausado": False,
        "ultimo_mensaje_bot": fecha,
    }

    assert eventos[0]["pedido"] is pedido
    assert eventos[0]["tipo_evento"] == (
        "bot_esperando_respuesta"
    )
    assert eventos[0]["canal"] == "whatsapp"
    assert eventos[0]["resultado"] == "ok"


def test_servicio_respeta_commit_false():
    pedido = PedidoFake()
    session = SessionFake()

    assert ia_marcar_mensaje_bot_service(
        pedido,
        "mercadolibre",
        lambda *args, **kwargs: None,
        lambda **kwargs: None,
        session,
        commit=False,
    ) is True

    assert session.commits == 0
    assert session.rollbacks == 0


def test_servicio_hace_rollback_si_falla():
    pedido = PedidoFake()
    session = SessionFake()

    def fallar(*args, **kwargs):
        raise RuntimeError("fallo controlado")

    assert ia_marcar_mensaje_bot_service(
        pedido,
        "whatsapp",
        fallar,
        lambda **kwargs: None,
        session,
    ) is False

    assert session.commits == 0
    assert session.rollbacks == 1


def test_wrapper_runtime_usa_dependencias_canonicas(
    monkeypatch,
):
    llamado = {}

    def servicio_fake(*args, **kwargs):
        llamado["args"] = args
        llamado["kwargs"] = kwargs
        return True

    monkeypatch.setattr(
        runtime,
        "ia_marcar_mensaje_bot_service",
        servicio_fake,
    )

    pedido = PedidoFake()

    assert runtime.ia_marcar_mensaje_bot(
        pedido,
        "whatsapp",
        texto="Hola",
        commit=False,
    ) is True

    assert llamado["args"] == (
        pedido,
        "whatsapp",
        runtime.actualizar_estado_conversacional_wa,
        runtime.registrar_evento_operativo_wa,
        runtime.db.session,
    )
    assert llamado["kwargs"] == {
        "texto": "Hola",
        "commit": False,
    }


def test_sender_no_importa_marcador_desde_app():
    sender = Path(
        "modules/whatsapp/sender.py"
    ).read_text(encoding="utf-8-sig")

    assert sender.count(
        "ia_marcar_mensaje_bot,"
    ) == 1
    assert (
        "from app import ia_marcar_mensaje_bot"
        not in sender
    )

def test_servicio_marca_respuesta_cliente_y_audita():
    pedido = PedidoFake()
    pedido.ia_esperando_respuesta = True
    pedido.ia_canal_activo = "whatsapp"

    session = SessionFake()
    fecha = datetime(2026, 7, 24, 16, 0, 0)
    estados = []
    eventos = []

    resultado = ia_marcar_respuesta_cliente_service(
        pedido,
        lambda *args, **kwargs: estados.append(
            (args, kwargs)
        ),
        lambda **kwargs: eventos.append(kwargs),
        session,
        canal=" whatsapp ",
        ahora_fn=lambda: fecha,
    )

    assert resultado is True
    assert pedido.ia_esperando_respuesta is False
    assert pedido.ia_ultimo_mensaje_cliente == fecha
    assert pedido.ia_canal_activo is None
    assert session.commits == 1
    assert session.rollbacks == 0

    assert estados[0][0] == (pedido,)
    assert estados[0][1] == {
        "canal_activo": "whatsapp",
        "estado_conversacional": "recolectando_datos",
        "ultimo_mensaje_cliente": fecha,
    }

    assert eventos[0]["pedido"] is pedido
    assert eventos[0]["tipo_evento"] == "cliente_respondio"
    assert eventos[0]["origen"] == "cliente"
    assert eventos[0]["canal"] == "whatsapp"
    assert eventos[0]["resultado"] == "ok"


def test_respuesta_cliente_respeta_commit_false():
    pedido = PedidoFake()
    session = SessionFake()

    assert ia_marcar_respuesta_cliente_service(
        pedido,
        lambda *args, **kwargs: None,
        lambda **kwargs: None,
        session,
        canal="mercadolibre",
        commit=False,
    ) is True

    assert session.commits == 0
    assert session.rollbacks == 0


def test_respuesta_cliente_hace_rollback_si_falla():
    pedido = PedidoFake()
    session = SessionFake()

    def fallar(*args, **kwargs):
        raise RuntimeError("fallo controlado")

    assert ia_marcar_respuesta_cliente_service(
        pedido,
        fallar,
        lambda **kwargs: None,
        session,
        canal="whatsapp",
    ) is False

    assert session.commits == 0
    assert session.rollbacks == 1


def test_wrapper_respuesta_cliente_usa_dependencias_canonicas(
    monkeypatch,
):
    llamado = {}

    def servicio_fake(*args, **kwargs):
        llamado["args"] = args
        llamado["kwargs"] = kwargs
        return True

    monkeypatch.setattr(
        runtime,
        "ia_marcar_respuesta_cliente_service",
        servicio_fake,
    )

    pedido = PedidoFake()

    assert runtime.ia_marcar_respuesta_cliente(
        pedido,
        canal="whatsapp",
        commit=False,
    ) is True

    assert llamado["args"] == (
        pedido,
        runtime.actualizar_estado_conversacional_wa,
        runtime.registrar_evento_operativo_wa,
        runtime.db.session,
    )
    assert llamado["kwargs"] == {
        "canal": "whatsapp",
        "commit": False,
    }


def test_webhook_no_importa_respuesta_cliente_desde_app():
    webhook = Path(
        "modules/whatsapp/webhook.py"
    ).read_text(encoding="utf-8-sig")

    assert "ia_marcar_respuesta_cliente," in webhook
    assert (
        "from app import ia_marcar_respuesta_cliente"
        not in webhook
    )
