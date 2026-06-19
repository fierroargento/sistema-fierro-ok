from domain.estados import Estado
from services.tracking_workflow import aplicar_estado_tracking_seguro_service


class PedidoFake:
    def __init__(self, canal, ml_tipo="", estado=Estado.DESPACHADO):
        self.canal = canal
        self.ml_tipo = ml_tipo
        self.estado = estado
        self.fecha_entregado = None
        self.ia_resumen = ""
        self.ia_requiere_operador = False
        self.ml_mensajes_pendientes = False


def test_tracking_entregado_ml_acordas_pasa_a_verificar_y_pide_operador():
    pedido = PedidoFake("Mercado Libre", "Acordás la Entrega")

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "entregado")

    assert nuevo_estado == Estado.VERIFICAR_DESTINO
    assert pedido.estado == Estado.VERIFICAR_DESTINO
    assert pedido.fecha_entregado is None
    assert pedido.ia_requiere_operador is True
    assert pedido.ml_mensajes_pendientes is True
    assert "avisar a Mercado Libre" in pedido.ia_resumen


def test_tracking_sucursal_ml_acordas_pasa_a_verificar_destino():
    pedido = PedidoFake("Mercado Libre", "Acordás la Entrega")

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "sucursal")

    assert nuevo_estado == Estado.VERIFICAR_DESTINO
    assert pedido.estado == Estado.VERIFICAR_DESTINO


def test_tracking_entregado_mercado_envios_no_cambia_estado():
    pedido = PedidoFake("Mercado Libre", "Mercado Envíos")

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "entregado")

    assert nuevo_estado is None
    assert pedido.estado == Estado.DESPACHADO
    assert pedido.fecha_entregado is None
    assert pedido.ia_requiere_operador is False
    assert pedido.ml_mensajes_pendientes is False


def test_tracking_sucursal_mercado_envios_no_cambia_estado():
    pedido = PedidoFake("Mercado Libre", "Mercado Envíos")

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "sucursal")

    assert nuevo_estado is None
    assert pedido.estado == Estado.DESPACHADO


def test_tracking_entregado_tienda_nube_no_cambia_estado():
    pedido = PedidoFake("Tienda Nube")

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "entregado")

    assert nuevo_estado is None
    assert pedido.estado == Estado.DESPACHADO
    assert pedido.fecha_entregado is None
