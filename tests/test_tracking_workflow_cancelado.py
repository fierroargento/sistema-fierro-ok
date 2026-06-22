from domain.estados import Estado
from services.tracking_workflow import aplicar_estado_tracking_seguro_service


class PedidoDummy:
    def __init__(
        self,
        estado=Estado.DESPACHADO,
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        ml_order_status="",
        ml_claim_status="",
        ml_claim_abierto=False,
        observaciones="",
    ):
        self.estado = estado
        self.canal = canal
        self.ml_tipo = ml_tipo
        self.ml_order_status = ml_order_status
        self.ml_claim_status = ml_claim_status
        self.ml_claim_abierto = ml_claim_abierto
        self.observaciones = observaciones
        self.ia_resumen = ""


def test_tracking_cancelado_post_despacho_con_claim_reembolso_cancela_pedido():
    pedido = PedidoDummy(
        estado=Estado.DESPACHADO,
        ml_claim_status="closed",
        ml_claim_abierto=True,
    )

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "cancelado")

    assert nuevo_estado == Estado.CANCELADO
    assert pedido.estado == Estado.CANCELADO
    assert "tracking del transporte informó cancelado" in pedido.observaciones


def test_tracking_cancelado_post_despacho_con_order_cancelada_cancela_pedido():
    pedido = PedidoDummy(
        estado=Estado.DESPACHADO,
        ml_order_status="cancelled",
    )

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "cancelado")

    assert nuevo_estado == Estado.CANCELADO
    assert pedido.estado == Estado.CANCELADO


def test_tracking_cancelado_post_despacho_sin_evidencia_ml_no_cancela():
    pedido = PedidoDummy(
        estado=Estado.DESPACHADO,
    )

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "cancelado")

    assert nuevo_estado is None
    assert pedido.estado == Estado.DESPACHADO


def test_tracking_cancelado_antes_de_despacho_no_cancela_por_tracking():
    pedido = PedidoDummy(
        estado=Estado.ETIQUETA_LISTA,
        ml_claim_status="closed",
        ml_claim_abierto=True,
    )

    nuevo_estado = aplicar_estado_tracking_seguro_service(pedido, "cancelado")

    assert nuevo_estado is None
    assert pedido.estado == Estado.ETIQUETA_LISTA
