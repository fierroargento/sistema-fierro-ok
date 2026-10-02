"""Lectura completa de packs ML, sin escrituras ni cambios de estado."""


def ml_agrupar_items(order_items):
    agrupados = {}
    for fila in order_items:
        item = fila.get("item") or {}
        sku = str(item.get("seller_sku") or item.get("seller_custom_field")
                  or item.get("id") or "").strip()
        cantidad = int(fila.get("quantity") or 0)
        if not sku or cantidad <= 0:
            raise ValueError("Pack ML incompleto: artículo sin SKU o cantidad válida.")
        if sku not in agrupados:
            agrupados[sku] = {**fila, "item": {**item, "seller_sku": sku}, "quantity": 0}
        agrupados[sku]["quantity"] += cantidad
    return list(agrupados.values())


def ml_obtener_ordenes_pack(pack_id, api_get, seller_id, shipping_id=""):
    pack_id = str(pack_id or "").strip()
    seller_id = str(seller_id or "").strip()
    if not pack_id or not seller_id:
        raise ValueError("Pack ML sin identificador o cuenta válida.")
    pack = api_get(f"/packs/{pack_id}")
    if str(pack.get("id") or "") != pack_id:
        raise ValueError("La respuesta ML no corresponde al pack solicitado.")
    referencias = pack.get("orders")
    if not isinstance(referencias, list) or not referencias:
        raise ValueError("Pack ML sin listado completo de órdenes.")
    ordenes = []
    vistos = set()
    for referencia in referencias:
        order_id = str((referencia.get("id") if isinstance(referencia, dict)
                        else referencia) or "").strip()
        if not order_id:
            raise ValueError("Pack ML con una referencia de orden inválida.")
        if order_id in vistos:
            continue
        vistos.add(order_id)
        order = api_get(f"/orders/{order_id}")
        if (str(order.get("id") or "") != order_id
                or str(order.get("pack_id") or "") != pack_id
                or str((order.get("seller") or {}).get("id") or "") != seller_id):
            raise ValueError("Una orden ML no corresponde al pack o a su cuenta.")
        if order.get("status") in {"cancelled", "invalid"}:
            continue
        if order.get("status") != "paid":
            raise ValueError("Pack ML pendiente: una orden todavía no está pagada.")
        if shipping_id and str((order.get("shipping") or {}).get("id") or "") != str(shipping_id):
            raise ValueError("Una orden del pack ML pertenece a otro envío.")
        if not isinstance(order.get("order_items"), list) or not order["order_items"]:
            raise ValueError("Pack ML incompleto: falta el detalle de una orden.")
        ml_agrupar_items(order["order_items"])
        ordenes.append(order)
    if not ordenes:
        raise ValueError("Pack ML sin órdenes pagadas para importar.")
    return ordenes


def ml_completar_order_pack(order, api_get, seller_id, shipping_id=""):
    pack_id = str(order.get("pack_id") or "").strip()
    if not pack_id:
        return order
    ordenes = ml_obtener_ordenes_pack(pack_id, api_get, seller_id, shipping_id)
    if str(order.get("id") or "") not in {str(o["id"]) for o in ordenes}:
        raise ValueError("La orden recibida no es una orden pagada del pack.")
    filas = [fila for o in ordenes for fila in o["order_items"]]
    return {**order, "order_items": ml_agrupar_items(filas)}


def ml_obtener_order_para_pedido(pedido, api_get, seller_id):
    order_id = str(pedido.id_venta or "").strip()
    pack_id = str(pedido.ml_pack_id or "").strip()
    if pack_id and order_id == pack_id:
        ordenes = ml_obtener_ordenes_pack(
            pack_id, api_get, seller_id, pedido.ml_shipping_id or "",
        )
        return ordenes[0]
    return api_get(f"/orders/{order_id}") if order_id else {}
