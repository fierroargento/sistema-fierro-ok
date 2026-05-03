"""
modules/whatsapp/scheduler.py
──────────────────────────────
Maneja los timers del bot:
- Recordatorio 1 a la hora sin respuesta
- Recordatorio 2 a las 3 horas sin respuesta  
- Escalado al operador después del recordatorio 2
- Siguiente producto de cross-sell a los 5 minutos sin respuesta

Se ejecuta periódicamente desde un job en app.py (cada 5 minutos es suficiente).
"""

from datetime import datetime, timedelta
from .config import (
    TIMER_PRIMER_RECORDATORIO,
    TIMER_SEGUNDO_RECORDATORIO,
    TIMER_CROSS_SELL_SIGUIENTE,
    modulo_activo,
)
from .flows import (
    wa_enviar_recordatorio_1,
    wa_enviar_recordatorio_2,
    wa_iniciar_cross_sell,
    wa_procesar_respuesta_cross_sell,
    _guardar_estado_wa,
)


def ejecutar_timers():
    """
    Revisa todos los pedidos con conversación WhatsApp activa
    y ejecuta las acciones que correspondan según el tiempo transcurrido.
    Llamar periódicamente cada 5 minutos.
    """
    if not modulo_activo():
        return

    try:
        from app import db, Pedido

        ahora = datetime.utcnow()

        # Buscar pedidos con conversación WA activa
        pedidos = (
            Pedido.query
            .filter(Pedido.wa_estado.isnot(None))
            .filter(Pedido.wa_estado != "")
            .filter(Pedido.wa_ultimo_contacto.isnot(None))
            .filter(Pedido.estado.notin_(["Entregado", "Cancelado"]))
            .all()
        )

        for pedido in pedidos:
            estado = str(pedido.wa_estado or "")
            ultimo = pedido.wa_ultimo_contacto
            if not ultimo:
                continue

            elapsed = (ahora - ultimo).total_seconds()

            # ── Recordatorios por no respuesta ──
            if estado == "esperando_confirmacion_sucursal":
                if elapsed >= TIMER_SEGUNDO_RECORDATORIO and not _ya_envio_recordatorio(pedido, 2):
                    wa_enviar_recordatorio_2(pedido)
                    _marcar_recordatorio(pedido, 2)

                elif elapsed >= TIMER_PRIMER_RECORDATORIO and not _ya_envio_recordatorio(pedido, 1):
                    wa_enviar_recordatorio_1(pedido)
                    _marcar_recordatorio(pedido, 1)

                # Después del recordatorio 2 sin respuesta → escalar operador
                elif elapsed >= TIMER_SEGUNDO_RECORDATORIO + 3600 and _ya_envio_recordatorio(pedido, 2):
                    _escalar_sin_respuesta(pedido)

            # ── Cross-sell: siguiente producto si no responde en 5 min ──
            elif estado.startswith("cross_sell:") and estado != "cross_sell_cerrado":
                if elapsed >= TIMER_CROSS_SELL_SIGUIENTE:
                    partes = estado.split(":")
                    sku_actual = partes[1] if len(partes) > 1 else ""
                    try:
                        indice = int(partes[-1]) if partes[-1].isdigit() else 0
                    except Exception:
                        indice = 0

                    from .cross_sell import obtener_productos_a_ofrecer, wa_ofrecer_producto, wa_cerrar_cross_sell
                    from app import normalizar_telefono
                    tel = normalizar_telefono(pedido.telefono)
                    productos = obtener_productos_a_ofrecer(pedido)
                    siguiente_idx = indice + 1

                    if siguiente_idx < len(productos):
                        siguiente_sku = productos[siguiente_idx]
                        _guardar_estado_wa(pedido, f"cross_sell:{siguiente_sku}:{siguiente_idx}")
                        wa_ofrecer_producto(tel, siguiente_sku)
                    else:
                        wa_cerrar_cross_sell(tel)
                        _guardar_estado_wa(pedido, "cross_sell_cerrado")

    except Exception as e:
        print("[WA SCHEDULER] Error:", e)


def _ya_envio_recordatorio(pedido, numero):
    """Checa si ya se envió el recordatorio N."""
    flag = getattr(pedido, f"wa_recordatorio_{numero}", None)
    return bool(flag)


def _marcar_recordatorio(pedido, numero):
    """Marca que ya se envió el recordatorio N."""
    try:
        from app import db
        setattr(pedido, f"wa_recordatorio_{numero}", True)
        pedido.wa_ultimo_contacto = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        print(f"[WA SCHEDULER] Error marcando recordatorio {numero}:", e)


def _escalar_sin_respuesta(pedido):
    """Escala al operador cuando el cliente no responde después de todos los intentos."""
    try:
        from app import db
        if pedido.ia_requiere_operador:
            return  # Ya está escalado
        pedido.ml_mensajes_pendientes = True
        pedido.ia_requiere_operador = True
        resumen = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen} | WA: Cliente no respondió confirmación de sucursal".strip(" |")
        pedido.wa_estado = "sin_respuesta_escalado"
        db.session.commit()
        print(f"[WA SCHEDULER] Pedido #{pedido.id} escalado por falta de respuesta")
    except Exception as e:
        print("[WA SCHEDULER] Error escalando:", e)
