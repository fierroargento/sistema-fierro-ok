"""Helpers puros de Tienda Nube.

IMPORTANTE: este modulo es preparatorio. No altera el runtime actual.
La migracion efectiva se hace de a bloques luego de validar el ancla.
"""

ESTADOS_TN_ENVIADO = {
    "fulfilled", "delivered", "shipped", "completed",
    "enviada", "enviado", "despachado", "despachada", "entregado", "entregada",
}

ESTADOS_TN_PAGO_OK = {"paid", "approved", "authorized", "received", "recibido"}

ESTADOS_TN_CANCELADO = {"cancelled", "canceled", "voided"}


def texto_multilenguaje(valor):
    if isinstance(valor, dict):
        return valor.get("es") or valor.get("pt") or valor.get("en") or next(iter(valor.values()), "")
    return valor or ""


def pago_confirmado(order):
    payment_status = str(order.get("payment_status") or order.get("financial_status") or "").lower().strip()
    return payment_status in ESTADOS_TN_PAGO_OK


def pedido_cancelado(order):
    status = str(order.get("status") or "").lower().strip()
    return bool(status in ESTADOS_TN_CANCELADO or order.get("cancelled_at"))


def pedido_ya_enviado(order):
    fulfillment_status = str(order.get("fulfillment_status") or order.get("shipping_status") or "").lower().strip()
    shipping_data = order.get("shipping") if isinstance(order.get("shipping"), dict) else {}
    shipping_status = str(
        shipping_data.get("status")
        or shipping_data.get("fulfillment_status")
        or shipping_data.get("shipment_status")
        or ""
    ).lower().strip()
    if fulfillment_status in ESTADOS_TN_ENVIADO or shipping_status in ESTADOS_TN_ENVIADO:
        return True
    texto = " ".join([fulfillment_status, shipping_status])
    return any(indicador in texto for indicador in ESTADOS_TN_ENVIADO)


def pedido_apto_para_fierro(order):
    if not order:
        return False, "pedido vacio"
    if pedido_cancelado(order):
        return False, "pedido cancelado"
    if not pago_confirmado(order):
        estado_pago = str(order.get("payment_status") or order.get("financial_status") or "sin estado")
        return False, f"pago no confirmado: {estado_pago}"
    if pedido_ya_enviado(order):
        return False, "pedido ya enviado/entregado"
    return True, "ok"
