"""
services/cross_sell_rules.py
────────────────────────────
Reglas comunes para decidir si corresponde iniciar cross-sell.

APB / SaaS:
- La decisión de iniciar cross-sell no debe estar duplicada entre ML, WA,
  operador manual y flujos automáticos.
- Los canales solo deben encargarse del envío.
- La regla de negocio vive acá.
"""

from domain.estados import Estado
from services.canal_manager import ml_acordas_via_cargo_bloquea_cross_sell


ESTADOS_SIN_CROSS_SELL = {
    Estado.DESPACHADO,
    Estado.VERIFICAR_DESTINO,
    Estado.LISTO_RETIRAR,
    Estado.DEMORA,
    Estado.RECLAMO,
    Estado.NO_ENTREGADO,
    Estado.ENTREGADO,
    Estado.FINALIZADO,
    Estado.CANCELADO,
    Estado.RECLAMAR_ML,
}


def pedido_en_etapa_sin_cross_sell(pedido):
    if not pedido:
        return True

    estado = getattr(pedido, "estado", None)

    return estado in ESTADOS_SIN_CROSS_SELL


def logistica_bloquea_cross_sell(pedido):
    """
    Devuelve True si la logística todavía no está suficientemente cerrada
    como para ofrecer agregados.

    Hoy reutiliza la regla APB ya existente en canal_manager:
    - ML / Acordás / no PP6040 sin sucursal.
    - ML / Acordás / PP6040 sin CP o transporte.
    - faltantes reales del recolector.
    - consulta logística pendiente sin definición.
    """
    return bool(ml_acordas_via_cargo_bloquea_cross_sell(pedido))


def motivo_bloqueo_cross_sell(
    pedido,
    modo="auto",
    auto_enabled=True,
    manual_enabled=True,
    forzar=False,
):
    """
    Devuelve "" si puede avanzar.
    Devuelve un texto/código si debe bloquearse.
    """
    modo = (modo or "auto").strip().lower()

    if not pedido:
        return "sin_pedido"

    if modo == "operador":
        if not manual_enabled and not forzar:
            return "cross_sell_manual_deshabilitado"
    else:
        if not auto_enabled:
            return "cross_sell_auto_deshabilitado"

    if pedido_en_etapa_sin_cross_sell(pedido):
        return "pedido_en_etapa_posterior"

    if logistica_bloquea_cross_sell(pedido):
        return "logistica_abierta"

    return ""


def puede_iniciar_cross_sell_pedido(
    pedido,
    modo="auto",
    auto_enabled=True,
    manual_enabled=True,
    forzar=False,
):
    return not motivo_bloqueo_cross_sell(
        pedido,
        modo=modo,
        auto_enabled=auto_enabled,
        manual_enabled=manual_enabled,
        forzar=forzar,
    )