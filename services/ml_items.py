from domain.estados import Estado


def ml_sincronizar_items_pedido_service(
    pedido,
    order,
    shipment,
    PedidoItem,
    db,
    ml_es_mercado_envios_order,
):
    order_items = (order or {}).get("order_items") or []

    existentes = {
        str(item.sku or "").strip(): item
        for item in pedido.items
    }

    usados = set()

    for order_item in order_items:
        item_data = order_item.get("item") or {}

        sku = str(
            item_data.get("seller_sku")
            or item_data.get("id")
            or ""
        ).strip()

        if not sku:
            sku = str(
                item_data.get("id")
                or "SIN-SKU"
            ).strip()

        descripcion = str(
            item_data.get("title")
            or "Producto ML"
        ).strip()

        cantidad = int(
            order_item.get("quantity")
            or 1
        )

        item = existentes.get(sku)

        if item is None:
            item = PedidoItem(
                sku=sku,
                descripcion=descripcion,
                cantidad=cantidad,
            )

            pedido.items.append(item)

        else:
            item.descripcion = descripcion
            item.cantidad = cantidad

        usados.add(sku)

    if (
        pedido.estado == Estado.CARGANDO
        and not ml_es_mercado_envios_order(order, shipment)
    ):
        for sku, item in list(existentes.items()):
            if sku not in usados:
                db.session.delete(item)

    return pedido