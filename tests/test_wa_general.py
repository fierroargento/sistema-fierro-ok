from datetime import timedelta
from types import SimpleNamespace

from services.fechas import ahora_utc_naive
from services.wa_general import (
    armar_conversaciones_wa_general,
    pedido_esta_activo_para_wa_general,
)


class QueryFake:
    def __init__(self, datos):
        self.datos = datos

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return self.datos


class CampoFake:
    def isnot(self, *args, **kwargs):
        return self

    def desc(self):
        return self


class ModeloMensajesFake:
    telefono = CampoFake()
    fecha = CampoFake()
    query = QueryFake([])


class ModeloPedidoFake:
    telefono = CampoFake()
    id = CampoFake()
    query = QueryFake([])


def mensaje(telefono, texto, fecha=None, direccion="in", estado="recibido"):
    return SimpleNamespace(
        telefono=telefono,
        texto=texto,
        fecha=fecha or ahora_utc_naive(),
        direccion=direccion,
        estado=estado,
    )


def pedido(id, telefono, estado, cliente="Cliente"):
    return SimpleNamespace(
        id=id,
        telefono=telefono,
        estado=estado,
        cliente=cliente,
    )


def test_pedido_activo_para_wa_general():
    assert pedido_esta_activo_para_wa_general(pedido(1, "111", "Despachado")) is True
    assert pedido_esta_activo_para_wa_general(pedido(2, "222", "Finalizado")) is False
    assert pedido_esta_activo_para_wa_general(pedido(3, "333", "Entregado")) is False


def test_wa_general_muestra_contacto_sin_pedido():
    ModeloMensajesFake.query = QueryFake([
        mensaje("5492920123456", "hola quiero comprar"),
    ])
    ModeloPedidoFake.query = QueryFake([])

    conversaciones = armar_conversaciones_wa_general(
        ModeloMensajesFake,
        ModeloPedidoFake,
    )

    assert len(conversaciones) == 1
    assert conversaciones[0].telefono == "5492920123456"
    assert conversaciones[0].ultimo_mensaje == "hola quiero comprar"
    assert conversaciones[0].pedido_contexto_id is None


def test_wa_general_no_muestra_telefono_con_pedido_activo():
    ModeloMensajesFake.query = QueryFake([
        mensaje("5492920123456", "hola"),
    ])
    ModeloPedidoFake.query = QueryFake([
        pedido(10, "5492920123456", "Despachado"),
    ])

    conversaciones = armar_conversaciones_wa_general(
        ModeloMensajesFake,
        ModeloPedidoFake,
    )

    assert conversaciones == []


def test_wa_general_muestra_telefono_con_pedido_finalizado():
    ModeloMensajesFake.query = QueryFake([
        mensaje("5492920123456", "necesito ayuda"),
    ])
    ModeloPedidoFake.query = QueryFake([
        pedido(20, "5492920123456", "Finalizado", cliente="Juan Perez"),
    ])

    conversaciones = armar_conversaciones_wa_general(
        ModeloMensajesFake,
        ModeloPedidoFake,
    )

    assert len(conversaciones) == 1
    assert conversaciones[0].nombre == "Juan Perez"
    assert conversaciones[0].pedido_contexto_id == 20
    assert conversaciones[0].pedido_contexto_estado == "Finalizado"
    assert len(conversaciones[0].pedidos_historicos) == 1


def test_wa_general_ordena_por_ultima_actividad():
    ahora = ahora_utc_naive()

    ModeloMensajesFake.query = QueryFake([
        mensaje("111", "viejo", fecha=ahora - timedelta(hours=2)),
        mensaje("222", "nuevo", fecha=ahora),
    ])
    ModeloPedidoFake.query = QueryFake([])

    conversaciones = armar_conversaciones_wa_general(
        ModeloMensajesFake,
        ModeloPedidoFake,
    )

    assert [c.telefono for c in conversaciones] == ["222", "111"]
