from services.fechas import ahora_utc_naive


def ml_actualizar_pedido_con_shipment_webhook(pedido, shipment, shipment_id=""):
    """Aplica datos de shipment ML a un pedido existente.

    No finaliza el pedido salvo que ML informe delivered/fulfilled.
    """

    shipment = shipment or {}
    shipment_id = str(
        shipment.get("id")
        or shipment_id
        or getattr(pedido, "ml_shipping_id", "")
        or ""
    ).strip()

    estado_shipping = str(
        shipment.get("status")
        or getattr(pedido, "ml_shipping_status", "")
        or ""
    ).lower().strip()

    if shipment_id:
        pedido.ml_shipping_id = shipment_id

    pedido.ml_shipping_status = estado_shipping
    pedido.ml_logistic_type = str(
        shipment.get("logistic_type")
        or getattr(pedido, "ml_logistic_type", "")
        or ""
    ).strip()
    pedido.ml_shipping_mode = str(
        shipment.get("mode")
        or getattr(pedido, "ml_shipping_mode", "")
        or ""
    ).strip()

    tracking_number = str(
        shipment.get("tracking_number")
        or ""
    ).strip()
    if tracking_number and not getattr(pedido, "seguimiento", None):
        pedido.seguimiento = tracking_number

    pedido.ultima_sync_ml = ahora_utc_naive()

    if (
        getattr(pedido, "ml_tipo", None) == "Mercado Envíos"
        and estado_shipping in ["delivered", "fulfilled"]
        and getattr(pedido, "estado", None) not in ["Finalizado", "Cancelado"]
    ):
        pedido.estado = "Finalizado"
        pedido.fecha_entregado = (
            getattr(pedido, "fecha_entregado", None)
            or ahora_utc_naive()
        )

        aviso = (
            "ML Mercado Envíos informa entregado. "
            "Pedido finalizado automáticamente."
        )
        obs = str(getattr(pedido, "observaciones", "") or "").strip()
        if aviso not in obs:
            pedido.observaciones = (
                f"{aviso} {obs}".strip()
            )[:300]

        return True

    return False
