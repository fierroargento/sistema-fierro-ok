"""
modules.bot_ml.mapeo_pedidos
----------------------------
Mapeos puros de order/shipment de Mercado Libre.

APB / SaaS:
- No consulta API.
- No escribe DB.
- No depende de Flask ni app.py.
- Recibe diccionarios order/shipment y devuelve datos normalizados.
"""


def ml_nombre_cliente(order, shipment=None):
    order = order or {}
    shipment = shipment or {}

    buyer = order.get("buyer") or {}
    receiver_address = shipment.get("receiver_address") or {}

    candidatos = [
        receiver_address.get("receiver_name"),
        receiver_address.get("recipient_name"),
        shipment.get("receiver_name"),
        order.get("receiver_name"),
        order.get("recipient_name"),
    ]

    nombre_buyer = " ".join([
        str(buyer.get("first_name") or "").strip(),
        str(buyer.get("last_name") or "").strip(),
    ]).strip()

    candidatos.append(nombre_buyer)

    for candidato in candidatos:
        valor = str(candidato or "").strip()
        if valor:
            return valor

    return str(buyer.get("nickname") or "Cliente Mercado Libre").strip()


def ml_mapear_tipo(order, shipment):
    order = order or {}
    shipment = shipment or {}

    shipping = order.get("shipping") or {}

    mode = str(
        shipping.get("mode")
        or shipment.get("mode")
        or ""
    ).lower().strip()

    logistic_type = str(
        shipment.get("logistic_type")
        or shipping.get("logistic_type")
        or ""
    ).lower().strip()

    if mode == "custom":
        return "Acordás la Entrega"

    if mode in ["me1", "me2", "fulfillment", "cross_docking", "drop_off"]:
        return "Mercado Envíos"

    if logistic_type in [
        "fulfillment",
        "cross_docking",
        "drop_off",
        "xd_drop_off",
        "self_service",
    ]:
        return "Mercado Envíos"

    return "Mercado Envíos" if shipping.get("id") else "Acordás la Entrega"


def ml_mapear_tipo_entrega(order, shipment):
    order = order or {}
    shipment = shipment or {}

    shipping_option = shipment.get("shipping_option") or {}
    delivery_type = str(
        shipping_option.get("delivery_type")
        or ""
    ).lower().strip()

    receiver_address = shipment.get("receiver_address") or {}

    if delivery_type == "pickup":
        return "Sucursal"

    if receiver_address.get("address_line"):
        return "Domicilio"

    return ""