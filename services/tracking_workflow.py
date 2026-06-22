from datetime import datetime, UTC

from domain.estados import Estado, ESTADOS_CERRADOS


MARCA_ENTREGADO_ML_ACORDAS = (
    "TRACKING: transporte informa entregado; confirmar entrega y avisar a Mercado Libre antes de cerrar"
)


def _es_ml_acordas(pedido):
    return (
        str(getattr(pedido, "canal", "") or "").strip() == "Mercado Libre"
        and str(getattr(pedido, "ml_tipo", "") or "").strip() == "Acordás la Entrega"
    )


def _marcar_pendiente_ml_acordas_entregado(pedido):
    resumen = (getattr(pedido, "ia_resumen", "") or "").strip()

    if MARCA_ENTREGADO_ML_ACORDAS not in resumen:
        pedido.ia_resumen = f"{resumen} | {MARCA_ENTREGADO_ML_ACORDAS}".strip(" |")[:1000]

    if hasattr(pedido, "ia_requiere_operador"):
        pedido.ia_requiere_operador = True

    if hasattr(pedido, "ml_mensajes_pendientes"):
        pedido.ml_mensajes_pendientes = True


ESTADOS_POST_DESPACHO_CANCELACION_CONFIRMADA = {
    Estado.DESPACHADO,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
    Estado.NO_ENTREGADO,
}

ML_ORDER_STATUS_CANCELADO = {
    "cancelled",
    "canceled",
    "invalid",
}

ML_CLAIM_STATUS_REEMBOLSO = {
    "closed",
    "resolved",
    "refunded",
    "buyer_won",
}


def _ml_confirma_cancelacion_o_reembolso(pedido):
    if not pedido:
        return False

    if str(getattr(pedido, "canal", "") or "").strip() != "Mercado Libre":
        return False

    order_status = str(getattr(pedido, "ml_order_status", "") or "").lower().strip()
    if order_status in ML_ORDER_STATUS_CANCELADO:
        return True

    claim_status = str(getattr(pedido, "ml_claim_status", "") or "").lower().strip()
    if claim_status in ML_CLAIM_STATUS_REEMBOLSO and getattr(pedido, "ml_claim_abierto", False):
        return True

    texto_evidencia = " ".join([
        str(getattr(pedido, "observaciones", "") or ""),
        str(getattr(pedido, "ia_resumen", "") or ""),
    ]).lower()

    return any(
        marca in texto_evidencia
        for marca in [
            "reembolso al comprador",
            "reclamo cerrado con reembolso",
            "refund",
            "money_back",
        ]
    )


def _marcar_cancelacion_confirmada_ml_tracking(pedido):
    pedido.estado = Estado.CANCELADO

    marca = (
        "Sistema canceló el pedido: ML confirmó reembolso/cancelación "
        "y el tracking del transporte informó cancelado."
    )

    observaciones = str(getattr(pedido, "observaciones", "") or "").strip()
    if marca not in observaciones:
        pedido.observaciones = (observaciones + "\n" + marca).strip()


def aplicar_estado_tracking_seguro_service(pedido, clasificacion):
    """Autoavanza solo cuando el tracking externo aplica al flujo correcto.

    Regla APB:
    - ML Acordás sí puede reaccionar al tracking externo de Correo.
    - Mercado Envíos, Tienda Nube y otros canales no deben cerrar ni avanzar por
      este tracking, porque tienen su propio flujo/webhook.
    """
    if not pedido or not clasificacion:
        return None

    if pedido.estado in ESTADOS_CERRADOS:
        return None

    if (
        clasificacion == "cancelado"
        and pedido.estado in ESTADOS_POST_DESPACHO_CANCELACION_CONFIRMADA
        and _ml_confirma_cancelacion_o_reembolso(pedido)
    ):
        _marcar_cancelacion_confirmada_ml_tracking(pedido)
        return Estado.CANCELADO

    if not _es_ml_acordas(pedido):
        return None

    if clasificacion == "entregado":
        _marcar_pendiente_ml_acordas_entregado(pedido)

        if pedido.estado in [
            Estado.DESPACHADO,
            Estado.DEMORA,
            Estado.RECLAMO,
            Estado.VERIFICAR_DESTINO,
        ]:
            if pedido.estado != Estado.VERIFICAR_DESTINO:
                pedido.estado = Estado.VERIFICAR_DESTINO
                return Estado.VERIFICAR_DESTINO
            return None

        return None

    if clasificacion == "sucursal" and pedido.estado in [
        Estado.DESPACHADO,
        Estado.DEMORA,
        Estado.RECLAMO,
    ]:
        pedido.estado = Estado.VERIFICAR_DESTINO
        return Estado.VERIFICAR_DESTINO

    return None
