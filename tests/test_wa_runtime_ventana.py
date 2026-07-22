from datetime import datetime, timedelta, UTC

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
