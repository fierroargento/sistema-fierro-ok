from pathlib import Path
from types import SimpleNamespace

from modules.whatsapp import runtime


class MensajeFake:
    def __init__(self, **campos):
        for nombre, valor in campos.items():
            setattr(self, nombre, valor)


class SessionFake:
    def __init__(self):
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, objeto):
        self.agregados.append(objeto)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class QueryFake:
    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return []


class CampoFake:
    def notin_(self, _valores):
        return self

    def desc(self):
        return self


class PedidoFake:
    estado = CampoFake()
    id = CampoFake()
    query = QueryFake()


def test_wrapper_conecta_dependencias_canonicas(monkeypatch):
    llamadas = []

    monkeypatch.setattr(
        runtime,
        "registrar_whatsapp_mensaje_service",
        lambda *args, **kwargs: llamadas.append(
            (args, kwargs)
        ) or "mensaje",
    )

    resultado = runtime.registrar_whatsapp_mensaje(
        telefono="2920123456",
        direccion="out",
        texto="Hola",
    )

    assert resultado == "mensaje"

    args, kwargs = llamadas[0]

    assert args == (
        runtime.WhatsAppMensaje,
        runtime.actualizar_estado_conversacional_wa,
        runtime.registrar_evento_operativo_wa,
        runtime.Pedido,
        runtime.db,
    )
    assert kwargs["telefono"] == "2920123456"
    assert kwargs["direccion"] == "out"
    assert kwargs["texto"] == "Hola"


def test_service_guarda_mensaje_y_actualiza_auditoria():
    session = SessionFake()
    db_fake = SimpleNamespace(session=session)
    pedido = SimpleNamespace(
        id=123,
        telefono="2920123456",
        wa_ultimo_contacto=None,
    )
    estados = []
    eventos = []

    resultado = runtime.registrar_whatsapp_mensaje_service(
        MensajeFake,
        lambda pedido, **kwargs: estados.append(
            (pedido, kwargs)
        ),
        lambda **kwargs: eventos.append(kwargs),
        PedidoFake,
        db_fake,
        pedido=pedido,
        telefono="2920123456",
        direccion="out",
        autor="bot",
        texto="Mensaje de prueba",
        estado="enviado",
    )

    assert resultado is session.agregados[0]
    assert resultado.pedido_id == 123
    assert resultado.direccion == "out"
    assert resultado.autor == "bot"
    assert resultado.texto == "Mensaje de prueba"
    assert resultado.estado == "enviado"

    assert session.commits == 1
    assert session.rollbacks == 0
    assert pedido.wa_ultimo_contacto is not None

    assert estados[0][0] is pedido
    assert estados[0][1]["canal_activo"] == "wa"
    assert estados[0][1]["ultimo_mensaje_bot"] is not None

    assert eventos[0]["pedido"] is pedido
    assert (
        eventos[0]["tipo_evento"]
        == "whatsapp_mensaje_registrado"
    )


def test_sender_y_webhook_no_importan_registro_desde_app():
    sender = Path(
        "modules/whatsapp/sender.py"
    ).read_text(encoding="utf-8-sig")
    webhook = Path(
        "modules/whatsapp/webhook.py"
    ).read_text(encoding="utf-8-sig")

    assert "registrar_whatsapp_mensaje," in sender
    assert "wa_ventana_24h_abierta," in sender
    assert (
        "from .runtime import registrar_whatsapp_mensaje"
        in webhook
    )

    assert (
        "from app import registrar_whatsapp_mensaje"
        not in sender
    )
    assert (
        "from app import registrar_whatsapp_mensaje"
        not in webhook
    )
