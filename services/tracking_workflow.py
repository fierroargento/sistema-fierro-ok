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
