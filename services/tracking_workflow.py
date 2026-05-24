from datetime import datetime, UTC

from domain.estados import Estado, ESTADOS_CERRADOS


def aplicar_estado_tracking_seguro_service(pedido, clasificacion):
    """Autoavanza solo cuando el estado logístico es claro."""
    if not pedido or not clasificacion:
        return None

    if pedido.estado in ESTADOS_CERRADOS:
        return None

    es_ml_acordas = (
        str(getattr(pedido, "canal", "") or "").strip() == "Mercado Libre"
        and str(getattr(pedido, "ml_tipo", "") or "").strip() == "Acordás la Entrega"
    )

    if clasificacion == "entregado" and pedido.estado not in [
        Estado.ENTREGADO,
        Estado.FINALIZADO,
    ]:
        if es_ml_acordas:
            if pedido.estado in [
                Estado.DESPACHADO,
                Estado.DEMORA,
                Estado.RECLAMO,
            ]:
                pedido.estado = Estado.VERIFICAR_DESTINO
                resumen = (getattr(pedido, "ia_resumen", "") or "").strip()
                marca = "TRACKING: transporte informa entregado; confirmar entrega y avisar a Mercado Libre antes de cerrar"
                if marca not in resumen:
                    pedido.ia_resumen = f"{resumen} | {marca}".strip(" |")[:1000]
                return Estado.VERIFICAR_DESTINO
            return None

        pedido.estado = Estado.ENTREGADO
        pedido.fecha_entregado = (
    pedido.fecha_entregado
    or datetime.now(UTC)
)
        return Estado.ENTREGADO

    if clasificacion == "sucursal" and pedido.estado in [
        Estado.DESPACHADO,
        Estado.DEMORA,
        Estado.RECLAMO,
    ]:
        pedido.estado = Estado.VERIFICAR_DESTINO
        return Estado.VERIFICAR_DESTINO

    return None