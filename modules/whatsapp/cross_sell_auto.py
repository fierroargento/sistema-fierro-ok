"""
modules/whatsapp/cross_sell_auto.py
──────────────────────────────────
Disparador central de cross-sell automático por WhatsApp.

APB / SaaS:
- El cross-sell automático debe intentarse cuando la IA/recolector cerró datos
  y la logística quedó definida.
- No debe repetirse si ya se inició para el pedido.
- La decisión de negocio vive en services/cross_sell_rules.py.
- Este módulo solo coordina el disparo por WhatsApp.
"""

from modules.whatsapp.config import CROSS_SELL_AUTO_ENABLED
from services.cross_sell_rules import motivo_bloqueo_cross_sell


def _cross_sell_ya_iniciado_por_estado(pedido):
    """
    Guard simple sin consultar DB:
    evita re-disparar si el pedido ya está en flujo cross-sell o cerrado.
    """
    if not pedido:
        return False

    wa_estado = str(getattr(pedido, "wa_estado", "") or "").strip().lower()
    ia_estado = str(getattr(pedido, "ia_recolector_estado", "") or "").strip().lower()

    estados_bloqueantes = {
        "cross_sell",
        "cross_sell_cerrado",
        "wa_cross_sell_cerrado",
    }

    return bool(
        wa_estado in estados_bloqueantes
        or ia_estado == "cross_sell"
    )


def _cross_sell_ya_iniciado_por_evento(pedido):
    """
    Guard con auditoría:
    si ya existe evento cross_sell_iniciado OK, no volver a disparar.

    Import local para no acoplar este módulo a app.py en import-time.
    """
    pedido_id = getattr(pedido, "id", None)

    if not pedido_id:
        return False

    try:
        from app import EventoOperativo

        evento = (
            EventoOperativo.query
            .filter_by(
                pedido_id=pedido_id,
                tipo_evento="cross_sell_iniciado",
                resultado="ok",
            )
            .first()
        )

        return evento is not None

    except Exception as e:
        print(f"[CROSS-SELL-AUTO] No se pudo verificar evento previo pedido #{pedido_id}: {e}")
        return False


def cross_sell_automatico_ya_iniciado(pedido):
    return bool(
        _cross_sell_ya_iniciado_por_estado(pedido)
        or _cross_sell_ya_iniciado_por_evento(pedido)
    )


def intentar_cross_sell_automatico(pedido, origen_disparo="datos_completos"):
    """
    Intenta iniciar cross-sell automático si las reglas centrales lo permiten.

    Devuelve:
    - (True, "cross_sell_iniciado")
    - (False, motivo)
    """
    pedido_id = getattr(pedido, "id", "?")

    motivo_bloqueo = motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=CROSS_SELL_AUTO_ENABLED,
        manual_enabled=True,
        forzar=False,
    )

    if motivo_bloqueo:
        print(
            f"[CROSS-SELL-AUTO] No inicia pedido #{pedido_id}: "
            f"{motivo_bloqueo}. Origen: {origen_disparo}"
        )
        return False, motivo_bloqueo

    if cross_sell_automatico_ya_iniciado(pedido):
        print(
            f"[CROSS-SELL-AUTO] No inicia pedido #{pedido_id}: "
            f"ya_iniciado. Origen: {origen_disparo}"
        )
        return False, "ya_iniciado"

    try:
        from modules.whatsapp.flows import wa_iniciar_cross_sell

        ok = wa_iniciar_cross_sell(
            pedido,
            origen="bot",
            forzar=False,
        )

        if ok:
            return True, "cross_sell_iniciado"

        return False, "wa_iniciar_cross_sell_rechazado"

    except Exception as e:
        print(f"[CROSS-SELL-AUTO] Error iniciando pedido #{pedido_id}: {e}")
        return False, "error"