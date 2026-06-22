import json


ML_ORDER_STATUS_CANCELADO = {
    "cancelled",
    "canceled",
    "invalid",
}

ML_PAYMENT_STATUS_REEMBOLSO = {
    "refunded",
    "partially_refunded",
    "charged_back",
    "cancelled",
    "canceled",
}

ML_PAYMENT_STATUS_DETAIL_REEMBOLSO = {
    "refunded",
    "partially_refunded",
    "charged_back",
    "reimbursed",
    "money_back",
}

ML_CLAIM_STATUS_REEMBOLSO = {
    "closed",
    "resolved",
    "refunded",
    "buyer_won",
}


MARCA_EVIDENCIA_ML_CANCELACION = (
    "ML informó cancelación/reembolso confirmado para este pedido."
)


def _normalizar(valor):
    return str(valor or "").lower().strip()


def ml_order_tiene_cancelacion_o_reembolso(order):
    if not isinstance(order, dict):
        return False

    status = _normalizar(order.get("status"))
    if status in ML_ORDER_STATUS_CANCELADO:
        return True

    if order.get("cancelled_at"):
        return True

    payments = order.get("payments") or []
    if not isinstance(payments, list):
        payments = []

    for payment in payments:
        if not isinstance(payment, dict):
            continue

        payment_status = _normalizar(payment.get("status"))
        payment_status_detail = _normalizar(payment.get("status_detail"))

        if payment_status in ML_PAYMENT_STATUS_REEMBOLSO:
            return True

        if payment_status_detail in ML_PAYMENT_STATUS_DETAIL_REEMBOLSO:
            return True

        for campo in [
            "transaction_amount_refunded",
            "amount_refunded",
            "refunded_amount",
        ]:
            try:
                if float(payment.get(campo) or 0) > 0:
                    return True
            except (TypeError, ValueError):
                pass

    return False


def ml_claim_tiene_reembolso(claim):
    if not isinstance(claim, dict):
        return False

    status = _normalizar(claim.get("status"))
    if status not in ML_CLAIM_STATUS_REEMBOLSO:
        return False

    resolution_raw = claim.get("resolution") or ""

    if isinstance(resolution_raw, dict):
        resolution = json.dumps(resolution_raw, ensure_ascii=False).lower()
    else:
        resolution = str(resolution_raw).lower()

    return any(
        palabra in resolution
        for palabra in [
            "refund",
            "refunded",
            "buyer",
            "return",
            "money_back",
            "devol",
            "reembolso",
        ]
    )


def marcar_evidencia_ml_cancelacion_en_pedido(pedido, motivo=None):
    if not pedido:
        return False

    observaciones = str(getattr(pedido, "observaciones", "") or "").strip()

    marca = MARCA_EVIDENCIA_ML_CANCELACION
    if motivo:
        marca = f"{marca} Motivo: {motivo}."

    if MARCA_EVIDENCIA_ML_CANCELACION in observaciones:
        return False

    pedido.observaciones = f"{observaciones}\n{marca}".strip()
    return True
