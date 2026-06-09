from domain.estados import Estado
from services.cross_sell_preparacion import (
    debe_bloquear_avance_por_agregado,
    debe_mostrar_en_inicio_carga_por_agregado,
    marcar_interes_cross_sell_preparacion,
    pedido_en_preparacion_cross_sell,
    resolver_agregado_pendiente,
    tiene_agregado_pendiente_en_preparacion,
)


class SessionFake:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class DbFake:
    def __init__(self):
        self.session = SessionFake()


class PedidoFake:
    def __init__(
        self,
        estado=Estado.ETIQUETA_LISTA,
        agregado_pendiente_revision=False,
    ):
        self.id = 1
        self.estado = estado
        self.agregado_pendiente_revision = agregado_pendiente_revision
        self.agregado_revision_fecha = None
        self.agregado_revision_usuario = None


def test_pedido_en_preparacion_cross_sell_solo_estados_validos():
    assert pedido_en_preparacion_cross_sell(PedidoFake(Estado.ETIQUETA_LISTA)) is True
    assert pedido_en_preparacion_cross_sell(PedidoFake(Estado.ETIQUETA_IMPRESA)) is True
    assert pedido_en_preparacion_cross_sell(PedidoFake(Estado.EMBALADO)) is True

    assert pedido_en_preparacion_cross_sell(PedidoFake(Estado.CARGANDO)) is False
    assert pedido_en_preparacion_cross_sell(PedidoFake(Estado.DESPACHADO)) is False
    assert pedido_en_preparacion_cross_sell(PedidoFake(Estado.ENTREGADO)) is False


def test_tiene_agregado_pendiente_en_preparacion():
    pedido = PedidoFake(
        estado=Estado.ETIQUETA_IMPRESA,
        agregado_pendiente_revision=True,
    )

    assert tiene_agregado_pendiente_en_preparacion(pedido) is True
    assert debe_mostrar_en_inicio_carga_por_agregado(pedido) is True
    assert debe_bloquear_avance_por_agregado(pedido) is True


def test_no_tiene_agregado_pendiente_si_ya_esta_despachado():
    pedido = PedidoFake(
        estado=Estado.DESPACHADO,
        agregado_pendiente_revision=True,
    )

    assert tiene_agregado_pendiente_en_preparacion(pedido) is False
    assert debe_mostrar_en_inicio_carga_por_agregado(pedido) is False
    assert debe_bloquear_avance_por_agregado(pedido) is False


def test_marcar_interes_cross_sell_preparacion_marca_pendiente_y_evento():
    pedido = PedidoFake(estado=Estado.EMBALADO)
    db = DbFake()
    eventos = []

    def registrar_evento(**kwargs):
        eventos.append(kwargs)

    ok = marcar_interes_cross_sell_preparacion(
        pedido,
        db,
        registrar_evento,
        sku="KITPACH",
        cantidad=1,
        texto_cliente="quiero ese",
    )

    assert ok is True
    assert pedido.agregado_pendiente_revision is True
    assert pedido.agregado_revision_fecha is None
    assert pedido.agregado_revision_usuario is None
    assert db.session.commits == 1

    assert len(eventos) == 1
    assert eventos[0]["tipo_evento"] == "cross_sell_cliente_interesado_preparacion"
    assert eventos[0]["payload"]["sku"] == "KITPACH"
    assert eventos[0]["payload"]["texto_cliente"] == "quiero ese"


def test_marcar_interes_no_aplica_si_esta_despachado():
    pedido = PedidoFake(estado=Estado.DESPACHADO)
    db = DbFake()
    eventos = []

    ok = marcar_interes_cross_sell_preparacion(
        pedido,
        db,
        lambda **kwargs: eventos.append(kwargs),
        sku="KITPACH",
    )

    assert ok is False
    assert pedido.agregado_pendiente_revision is False
    assert db.session.commits == 0
    assert eventos == []


def test_resolver_agregado_pendiente_limpia_bloqueo():
    pedido = PedidoFake(
        estado=Estado.ETIQUETA_LISTA,
        agregado_pendiente_revision=True,
    )
    db = DbFake()
    eventos = []
    auditorias = []

    ok, mensaje = resolver_agregado_pendiente(
        pedido,
        db,
        usuario="martin",
        resultado="sin_agregado",
        observacion="Cliente no quiso agregar.",
        registrar_evento=lambda **kwargs: eventos.append(kwargs),
        registrar_auditoria=lambda *args, **kwargs: auditorias.append((args, kwargs)),
    )

    assert ok is True
    assert "Despacho puede continuar" in mensaje
    assert pedido.agregado_pendiente_revision is False
    assert pedido.agregado_revision_fecha is not None
    assert pedido.agregado_revision_usuario == "martin"
    assert db.session.commits == 1

    assert len(eventos) == 1
    assert eventos[0]["tipo_evento"] == "cross_sell_cerrado_sin_agregado"

    assert len(auditorias) == 1


def test_resolver_agregado_pendiente_rechaza_resultado_invalido():
    pedido = PedidoFake(
        estado=Estado.ETIQUETA_LISTA,
        agregado_pendiente_revision=True,
    )
    db = DbFake()

    ok, mensaje = resolver_agregado_pendiente(
        pedido,
        db,
        usuario="martin",
        resultado="cualquier_cosa",
    )

    assert ok is False
    assert mensaje == "Resultado de resolución inválido."
    assert pedido.agregado_pendiente_revision is True
    assert db.session.commits == 0


def test_resolver_agregado_pendiente_rechaza_si_no_hay_pendiente():
    pedido = PedidoFake(
        estado=Estado.ETIQUETA_LISTA,
        agregado_pendiente_revision=False,
    )
    db = DbFake()

    ok, mensaje = resolver_agregado_pendiente(
        pedido,
        db,
        usuario="martin",
        resultado="sin_agregado",
    )

    assert ok is False
    assert mensaje == "El pedido no tiene agregado pendiente."
    assert db.session.commits == 0