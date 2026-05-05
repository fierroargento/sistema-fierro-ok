"""
modules/whatsapp/post_despacho.py
─────────────────────────────────
Motor de eventos post-despacho.

No reemplaza el flujo validado del sistema: solo reacciona ante cambios claros de tracking.
"""

from datetime import datetime

from .flows import wa_enviar_listo_para_retirar, wa_enviar_postventa


def registrar_tracking_evento(pedido, empresa, seguimiento, estado, clasificacion, raw_json=None, origen="scheduler"):
    """Guarda historial de tracking si existe el modelo TrackingEvento."""
    try:
        from app import db, TrackingEvento
        existe = TrackingEvento.query.filter_by(
            pedido_id=pedido.id,
            empresa=(empresa or "")[:80],
            seguimiento=(seguimiento or "")[:100],
            estado=(estado or "")[:300],
        ).first()
        if existe:
            return False
        ev = TrackingEvento(
            pedido_id=pedido.id,
            empresa=(empresa or "")[:80],
            seguimiento=(seguimiento or "")[:100],
            estado=(estado or "")[:300],
            clasificacion=(clasificacion or "")[:50],
            raw_json=raw_json,
            origen=(origen or "scheduler")[:50],
            fecha_evento=datetime.utcnow(),
        )
        db.session.add(ev)
        return True
    except Exception as e:
        print("[POST DESPACHO] No se pudo guardar TrackingEvento:", e)
        return False


def procesar_evento_tracking_pedido(pedido, clasificacion, estado_externo, origen="scheduler"):
    """Dispara mensajes y acciones seguras según clasificación logística."""
    if not pedido or not clasificacion:
        return []

    acciones = []
    try:
        from app import db

        # Listo para retirar: avisar una sola vez.
        if clasificacion == "sucursal":
            if not getattr(pedido, "wa_listo_retirar_enviado", False):
                if wa_enviar_listo_para_retirar(pedido):
                    acciones.append("wa_listo_para_retirar")
            return acciones

        # Incidencias: escalar operador, no mandar mensaje riesgoso automático.
        if clasificacion == "incidencia":
            pedido.ia_requiere_operador = True
            pedido.ml_mensajes_pendientes = True
            resumen = (pedido.ia_resumen or "").strip()
            pedido.ia_resumen = f"{resumen} | TRACKING: incidencia detectada ({estado_externo})".strip(" |")
            acciones.append("escalado_incidencia")
            return acciones

        # Entregado: postventa/fidelización una sola vez.
        if clasificacion == "entregado":
            if not getattr(pedido, "fecha_entregado", None):
                pedido.fecha_entregado = datetime.utcnow()
            if not getattr(pedido, "wa_postventa_enviada", False):
                if wa_enviar_postventa(pedido):
                    acciones.append("wa_postventa")

            # Si NO es ML Acordás, puede quedar finalizado según reglas actuales.
            # Si es ML Acordás, NO cerrar: debe quedar Entregado para permitir "Avisar a Mercado Libre".
            canal = str(getattr(pedido, "canal", "") or "")
            ml_tipo = str(getattr(pedido, "ml_tipo", "") or "")
            if not (canal == "Mercado Libre" and ml_tipo == "Acordás la Entrega"):
                if pedido.estado == "Entregado":
                    pedido.estado = "Finalizado"
                    acciones.append("finalizado_auto")
            else:
                acciones.append("pendiente_avisar_ml")
            return acciones

        return acciones

    except Exception as e:
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        print("[POST DESPACHO] Error procesando evento:", e)
        return acciones
