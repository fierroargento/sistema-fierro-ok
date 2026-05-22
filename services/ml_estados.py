def ml_estado_order_service(order):
    return str(
        (order or {}).get("status") or ""
    ).lower().strip()


def ml_estado_shipment_service(
    order=None,
    shipment=None,
):
    order = order or {}
    shipment = shipment or {}

    shipping = order.get("shipping") or {}

    return str(
        shipment.get("status")
        or shipping.get("status")
        or ""
    ).lower().strip()


def ml_order_esta_entregado_service(
    order,
    shipment=None,
    ml_estado_order=None,
    ml_estado_shipment=None,
):
    """
    Detecta entregas reales informadas por Mercado Libre.

    APB:
    - Mercado Envíos puede finalizar con shipment delivered/fulfilled.
    - Acordás la Entrega NO debe finalizar por order closed.
    """

    order = order or {}
    shipment = shipment or {}

    estado_order = ml_estado_order(order)
    estado_shipping = ml_estado_shipment(
        order,
        shipment,
    )

    tags = {
        str(t or "").lower().strip()
        for t in (order.get("tags") or [])
    }

    shipping = order.get("shipping") or {}

    logistic_type = str(
        shipment.get("logistic_type")
        or shipping.get("logistic_type")
        or ""
    ).lower().strip()

    es_mercado_envios = logistic_type in [
        "fulfillment",
        "cross_docking",
        "drop_off",
        "xd_drop_off",
        "self_service",
    ]

    if estado_shipping in {
        "delivered",
        "fulfilled",
    }:
        return True

    if estado_order in {
        "delivered",
        "fulfilled",
    }:
        return True

    if tags.intersection({
        "delivered",
        "fulfilled",
    }):
        return True

    # APB:
    # Nunca interpretar "closed"
    # como entregado para Acordás.

    if (
        es_mercado_envios
        and estado_order == "closed"
    ):

        tags_cancelacion = {
            "cancelled",
            "canceled",
            "refunded",
            "invalid",
        }

        if not tags.intersection(tags_cancelacion):
            return True

    return False

def ml_logistica_no_operable_service(order, shipment):
    order = order or {}
    shipment = shipment or {}

    shipping = order.get("shipping") or {}
    tags = order.get("tags") or []

    valores = [
        shipment.get("logistic_type"),
        shipment.get("mode"),
        shipping.get("logistic_type"),
        shipping.get("mode"),
    ]

    valores_normalizados = [
        str(v or "").lower().strip()
        for v in valores
    ]

    tags_normalizados = [
        str(t or "").lower().strip()
        for t in tags
    ]

    if (
        "fulfillment" in valores_normalizados
        or "fulfillment" in tags_normalizados
        or "meli_full" in tags_normalizados
        or "mercado_envios_full" in tags_normalizados
        or "full" in tags_normalizados
    ):
        return True, "Mercado Envíos Full"

    if (
        "self_service" in valores_normalizados
        or "self_service" in tags_normalizados
        or "flex" in valores_normalizados
        or "flex" in tags_normalizados
        or "mercado_envios_flex" in tags_normalizados
    ):
        return True, "Mercado Envíos Flex"

    return False, ""


def ml_es_envio_full_service(
    order,
    shipment,
    ml_logistica_no_operable,
):
    no_operable, motivo = ml_logistica_no_operable(
        order,
        shipment,
    )

    return no_operable and motivo == "Mercado Envíos Full"


def ml_es_mercado_envios_order_service(
    order,
    shipment,
    ml_mapear_tipo,
):
    return ml_mapear_tipo(
        order or {},
        shipment or {},
    ) == "Mercado Envíos"


def ml_envio_ya_despachado_service(
    order,
    shipment=None,
):
    shipment = shipment or {}
    shipping = (order or {}).get("shipping") or {}

    estados = {
        str(shipment.get("status") or "").lower().strip(),
        str(shipping.get("status") or "").lower().strip(),
    }

    estados.discard("")

    return bool(
        estados.intersection({
            "shipped",
            "delivered",
            "not_delivered",
            "cancelled",
            "returned",
        })
    )

def ml_order_debe_omitirse_service(
    order,
    shipment=None,
    ml_pedido_esta_ignorado=None,
    ml_order_esta_entregado=None,
    ml_estado_order=None,
    ml_logistica_no_operable=None,
):
    order_id = str(
        (order or {}).get("id") or ""
    ).strip()

    if not order_id:
        return True, "sin ID de orden"

    if ml_pedido_esta_ignorado(order_id):
        return True, "pedido eliminado manualmente en Fierro"

    # Si está entregado en ML y llega a esta validación,
    # no es una venta operativa nueva.
    if ml_order_esta_entregado(
        order,
        shipment,
    ):
        return True, "ML entregado/histórico — no se importa como pedido operativo nuevo"

    estado = ml_estado_order(order)

    if estado in [
        "cancelled",
        "invalid",
        "closed",
    ]:
        return True, (
            f"estado ML {estado} — orden ya finalizada/no operable en ML, "
            "no se importa"
        )

    no_operable, motivo = ml_logistica_no_operable(
        order,
        shipment or {},
    )

    if no_operable:
        return True, motivo

    return False, "" 

from datetime import datetime, UTC

from domain.estados import Estado


def ml_marcar_pedido_finalizado_por_entrega_service(
    pedido,
    order,
    shipment=None,
    ml_estado_order=None,
    ml_estado_shipment=None,
):
    """Mantiene la venta en Histórico cuando ML ya la informa como entregada."""

    if not pedido:
        return None

    shipment = shipment or {}

    estado_order = ml_estado_order(order)
    estado_shipping = ml_estado_shipment(
        order,
        shipment,
    )

    pedido.origen = "mercadolibre"
    pedido.canal = "Mercado Libre"
    pedido.id_venta = str(
        (order or {}).get("id")
        or pedido.id_venta
        or ""
    ).strip()

    pedido.ml_order_status = (
        estado_order
        or pedido.ml_order_status
    )

    if estado_shipping:
        pedido.ml_shipping_status = estado_shipping

    ahora = datetime.now(UTC)

    pedido.estado = Estado.FINALIZADO
    pedido.fecha_entregado = pedido.fecha_entregado or ahora
    pedido.ultima_sync_ml = ahora

    aviso = (
        "ML informa venta entregada. "
        "Pedido movido automáticamente a Histórico/Finalizado."
    )

    obs = str(
        pedido.observaciones or ""
    ).strip()

    if aviso not in obs:
        pedido.observaciones = (
            f"{aviso} {obs}".strip()
        )[:300]

    return pedido   