"""
modules/whatsapp/webhook.py
────────────────────────────
Endpoint que recibe mensajes entrantes de Meta y los deriva al flujo correcto.
"""

import json
import re
from flask import request, jsonify

from .config import WA_VERIFY_TOKEN, modulo_activo
from .flows import (
    wa_procesar_respuesta_confirmacion,
    wa_procesar_datos_recibidos,
    wa_procesar_respuesta_cross_sell,
    wa_procesar_respuesta_postventa,
)


def _obtener_estado_wa(pedido):
    return str(getattr(pedido, "wa_estado", "") or "")


def _buscar_pedido_por_telefono(telefono):
    """Busca el pedido activo más reciente asociado a ese número."""
    from app import Pedido, normalizar_telefono
    tel_norm = normalizar_telefono(telefono)
    if not tel_norm:
        return None

    return (
        Pedido.query
        .filter(Pedido.telefono.ilike(f"%{tel_norm[-8:]}%"))
        .filter(Pedido.estado.notin_(["Entregado", "Cancelado"]))
        .order_by(Pedido.id.desc())
        .first()
    )


def _routear_mensaje(pedido, texto, telefono):
    """
    Decide qué flujo manejar según el estado actual del pedido.
    """
    estado = _obtener_estado_wa(pedido)

    # Sin pedido activo
    if not pedido:
        from .sender import wa_enviar_texto
        from app import normalizar_telefono
        tel = normalizar_telefono(telefono)
        wa_enviar_texto(
            tel,
            "¡Hola! 👋 No encontramos un pedido activo asociado a este número. "
            "Si tenés una consulta escribinos y un operador te ayuda a la brevedad 😊"
        )
        return

    # Esperando confirmación de sucursal
    if estado == "esperando_confirmacion_sucursal":
        wa_procesar_respuesta_confirmacion(pedido, texto)
        return

    # Esperando datos faltantes
    if estado == "esperando_datos":
        wa_procesar_datos_recibidos(pedido, texto)
        return

    # Cross-sell activo
    if estado.startswith("cross_sell:") and estado != "cross_sell_cerrado":
        partes = estado.split(":")
        sku_actual = partes[1] if len(partes) > 1 else ""
        try:
            indice = int(partes[-1]) if partes[-1].isdigit() else 0
        except Exception:
            indice = 0
        wa_procesar_respuesta_cross_sell(pedido, texto, sku_actual, indice)
        return

    # Postventa
    if estado == "postventa":
        wa_procesar_respuesta_postventa(pedido, texto)
        return

    # Estado no reconocido o vacío → IA o escala
    from .flows import _wa_responder_con_ia
    from app import normalizar_telefono
    _wa_responder_con_ia(pedido, texto, normalizar_telefono(telefono))


def registrar_webhook(app):
    """
    Registra el endpoint /webhook/whatsapp en la app Flask.
    Solo se activa si el módulo está configurado en el .env.
    """
    if not modulo_activo():
        print("[WA] Módulo WhatsApp inactivo — configurar .env para activar")
        return

    @app.route("/webhook/whatsapp", methods=["GET", "POST"])
    def webhook_whatsapp():

        # ── Verificación inicial de Meta ──
        if request.method == "GET":
            mode      = request.args.get("hub.mode")
            token     = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            if mode == "subscribe" and token == WA_VERIFY_TOKEN:
                print("[WA] Webhook verificado por Meta ✓")
                return challenge, 200
            return "Token inválido", 403

        # ── Mensajes entrantes ──
        try:
            data = request.get_json(silent=True) or {}
            print("[WA] Webhook:", json.dumps(data)[:300])

            entry   = (data.get("entry") or [{}])[0]
            changes = (entry.get("changes") or [{}])[0]
            value   = changes.get("value") or {}
            messages = value.get("messages") or []

            for msg in messages:
                tipo     = msg.get("type")
                telefono = msg.get("from", "")

                if tipo == "text":
                    texto = (msg.get("text") or {}).get("body", "").strip()
                elif tipo == "interactive":
                    inter = msg.get("interactive") or {}
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    texto = reply.get("title", "").strip()
                else:
                    continue

                if texto:
                    pedido = _buscar_pedido_por_telefono(telefono)
                    _routear_mensaje(pedido, texto, telefono)

        except Exception as e:
            print("[WA] Error procesando webhook:", e)

        # Meta requiere siempre 200
        return jsonify({"status": "ok"}), 200

    print("[WA] Webhook WhatsApp registrado en /webhook/whatsapp ✓")
