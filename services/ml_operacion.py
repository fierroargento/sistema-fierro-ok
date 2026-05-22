from datetime import datetime, UTC


def ml_validar_orden_operable_antes_de_despacho_service(
    pedido,
    db,
    ml_obtener_order,
    ml_obtener_shipment,
    ml_obtener_claim_de_order,
    ml_marcar_claim_en_pedido,
):
    """
    Revalida en vivo contra Mercado Libre antes de embalar o despachar.
    Evita operar pedidos que se cancelaron o cambiaron de estado en ML
    entre la última sincronización y la acción del operador.
    """

    if not pedido or pedido.canal != "Mercado Libre" or not pedido.id_venta:
        return True, ""

    try:
        order = ml_obtener_order(pedido.id_venta)

        if not order:
            return True, ""

        estado_order = str(order.get("status") or "").lower().strip()
        pedido.ml_order_status = estado_order or pedido.ml_order_status

        shipping = order.get("shipping") or {}
        shipping_id = str(
            shipping.get("id")
            or pedido.ml_shipping_id
            or ""
        ).strip()

        shipment = (
            ml_obtener_shipment(shipping_id)
            if shipping_id
            else {}
        )

        estado_shipping = str(
            (shipment or {}).get("status")
            or shipping.get("status")
            or ""
        ).lower().strip()

        if estado_shipping:
            pedido.ml_shipping_status = estado_shipping

        if shipping_id:
            pedido.ml_shipping_id = shipping_id

        pedido.ultima_sync_ml = datetime.now(UTC)

        estados_order_bloqueados = {
            "cancelled",
            "invalid",
        }

        estados_shipping_bloqueados = {
            "cancelled",
            "not_delivered",
            "returned",
        }

        estados_shipping_ya_operados = {
            "shipped",
            "delivered",
        }

        if estado_order in estados_order_bloqueados:
            db.session.commit()
            return False, (
                f"Mercado Libre informa que la venta esta {estado_order}. "
                "No corresponde embalar ni despachar."
            )

        if estado_shipping in estados_shipping_bloqueados:
            db.session.commit()
            return False, (
                f"Mercado Libre informa que el envio esta {estado_shipping}. "
                "No corresponde embalar ni despachar."
            )

        if (
            pedido.ml_tipo == "Mercado Envíos"
            and estado_shipping in estados_shipping_ya_operados
        ):
            db.session.commit()
            return False, (
                f"Mercado Libre informa que el envio ya figura {estado_shipping}. "
                "Revisar la venta antes de operar."
            )

        # APB: bloquear operación si ML tiene reclamo activo.
        if getattr(pedido, "ml_claim_abierto", False):
            db.session.commit()
            return False, (
                f"Este pedido tiene un reclamo activo en Mercado Libre "
                f"(ID: {pedido.ml_claim_id or 'sin ID'}). "
                "No corresponde embalar ni despachar. Atender el reclamo primero."
            )

        claim_live = ml_obtener_claim_de_order(
            pedido.id_venta,
            getattr(pedido, "ml_pack_id", "") or "",
        )

        if claim_live:
            ml_marcar_claim_en_pedido(
                pedido,
                claim_live,
            )

            db.session.commit()

            return False, (
                f"Mercado Libre reporta un reclamo activo "
                f"({claim_live.get('reason_id') or claim_live.get('type') or 'sin motivo informado'}). "
                "No corresponde embalar ni despachar. Atender el reclamo primero."
            )

        db.session.commit()

        return True, ""

    except Exception as e:
        db.session.rollback()
        print(
            "No se pudo revalidar orden ML antes de embalar/despachar:",
            e,
        )
        return True, ""