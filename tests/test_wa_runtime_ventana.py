from datetime import datetime, timedelta, UTC

from modules.whatsapp import runtime
from modules.whatsapp.runtime import wa_ventana_24h_abierta_service
from services.fechas import ahora_utc_naive


class FakeQuery:
    def __init__(self, mensaje):
        self.mensaje = mensaje

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.mensaje


class FakeColumn:
    def __eq__(self, other):
        return True

    def desc(self):
        return self


class FakeWhatsAppMensaje:
    direccion = FakeColumn()
    pedido_id = FakeColumn()
    telefono = FakeColumn()
    fecha = FakeColumn()
    query = None


class MensajeFake:
    def __init__(self, fecha):
        self.fecha = fecha


class PedidoFake:
    id = 123
    telefono = "2920123456"


def test_wa_ventana_24h_abierta_service_acepta_fecha_aware_reciente():
    FakeWhatsAppMensaje.query = FakeQuery(
        MensajeFake(datetime.now(UTC) - timedelta(minutes=10))
    )

    assert wa_ventana_24h_abierta_service(
        FakeWhatsAppMensaje,
        pedido=PedidoFake(),
    ) is True


def test_wa_ventana_24h_abierta_service_acepta_fecha_naive_reciente():
    FakeWhatsAppMensaje.query = FakeQuery(
        MensajeFake(ahora_utc_naive() - timedelta(minutes=10))
    )

    assert wa_ventana_24h_abierta_service(
        FakeWhatsAppMensaje,
        pedido=PedidoFake(),
    ) is True


def test_wa_ventana_24h_abierta_service_rechaza_fecha_vieja():
    FakeWhatsAppMensaje.query = FakeQuery(
        MensajeFake(ahora_utc_naive() - timedelta(hours=25))
    )

    assert wa_ventana_24h_abierta_service(
        FakeWhatsAppMensaje,
        pedido=PedidoFake(),
    ) is False

def test_wa_ventana_24h_abierta_usa_modelo_canonico(monkeypatch):
    llamado = {}

    def servicio_fake(
        modelo,
        pedido=None,
        telefono="",
    ):
        llamado["modelo"] = modelo
        llamado["pedido"] = pedido
        llamado["telefono"] = telefono
        return True

    monkeypatch.setattr(
        runtime,
        "wa_ventana_24h_abierta_service",
        servicio_fake,
    )

    pedido = PedidoFake()

    assert runtime.wa_ventana_24h_abierta(
        pedido=pedido,
        telefono="2920123456",
    ) is True

    assert llamado == {
        "modelo": runtime.WhatsAppMensaje,
        "pedido": pedido,
        "telefono": "2920123456",
    }


def test_sender_no_importa_ventana_24h_desde_app():
    from pathlib import Path

    texto = Path(
        "modules/whatsapp/sender.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "wa_ventana_24h_abierta,"
    ) == 1
    assert (
        "from app import ia_puede_enviar_automatico, "
        "wa_ventana_24h_abierta"
        not in texto
    )
