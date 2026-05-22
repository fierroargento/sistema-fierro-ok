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