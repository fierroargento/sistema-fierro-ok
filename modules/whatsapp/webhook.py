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
    wa_procesar_eleccion_transporte,
    _responder_factura_o_escalar,
)


def _obtener_estado_wa(pedido):
    return str(getattr(pedido, "wa_estado", "") or "")


def _buscar_pedido_por_telefono(telefono):
    """Busca el pedido activo más reciente asociado a ese número."""
    from app import buscar_pedido_activo_por_telefono
    return buscar_pedido_activo_por_telefono(telefono)



def _normalizar_estado_meta(estado):
    estado = str(estado or "").strip().lower()
    mapa = {
        "sent": "enviado",
        "delivered": "entregado",
        "read": "leido",
        "failed": "error",
    }
    return mapa.get(estado, estado or "pendiente")


def _procesar_statuses_whatsapp(statuses):
    """
    Actualiza el historial interno de WhatsApp con los estados que envía Meta.
    Meta informa estos eventos para mensajes salientes: sent, delivered, read, failed.
    """
    if not statuses:
        return

    try:
        from app import db, WhatsAppMensaje
    except Exception as e:
        print("[WA-STATUS] No se pudo importar db/WhatsAppMensaje:", e)
        return

    hubo_cambios = False

    for status in statuses:
        message_id = str(status.get("id") or "").strip()
        estado_meta = str(status.get("status") or "").strip().lower()
        estado_normalizado = _normalizar_estado_meta(estado_meta)

        if not message_id:
            continue

        try:
            msg = WhatsAppMensaje.query.filter_by(message_id_meta=message_id).first()
            if not msg:
                print(f"[WA-STATUS] No se encontró mensaje para id Meta {message_id} estado={estado_meta}")
                continue

            # APB: no degradar estados. Si ya fue leído, no volver a entregado/enviado.
            prioridad = {"pendiente": 0, "enviado": 1, "entregado": 2, "leido": 3, "error": 4, "recibido": 5}
            estado_actual = str(msg.estado or "").strip().lower()

            if estado_normalizado == "error":
                errores = status.get("errors") or []
                if errores:
                    try:
                        msg.error = json.dumps(errores, ensure_ascii=False)[:1000]
                    except Exception:
                        msg.error = str(errores)[:1000]
                msg.estado = "error"
                hubo_cambios = True
                continue

            if prioridad.get(estado_normalizado, 0) >= prioridad.get(estado_actual, 0):
                msg.estado = estado_normalizado
                if estado_normalizado in ["enviado", "entregado", "leido"]:
                    msg.error = ""
                hubo_cambios = True

        except Exception as e:
            print(f"[WA-STATUS] Error procesando estado {estado_meta} para {message_id}:", e)

    if hubo_cambios:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("[WA-STATUS] Error guardando estados:", e)

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

    # Si un operador tomó la conversación, el bot NO responde automático.
    if estado == "operador_manual":
        try:
            from app import db
            pedido.ml_mensajes_pendientes = True
            pedido.ml_mensajes_pendientes_count = (pedido.ml_mensajes_pendientes_count or 0) + 1
            pedido.ia_requiere_operador = True
            db.session.commit()
        except Exception as e:
            print("[WA] No se pudo marcar pendiente operador:", e)
        return

    # Preguntas simples de factura: respuesta fija en cualquier estado activo
    if any(x in (texto or "").lower() for x in ["factura", "facturacion", "facturación", "factura a", "factura b"]):
        _responder_factura_o_escalar(pedido, texto)
        return

    # Esperando confirmación de sucursal legacy
    if estado == "esperando_confirmacion_sucursal":
        wa_procesar_respuesta_confirmacion(pedido, texto)
        return

    # Esperando elección de sucursal/punto Correo o domicilio
    if estado == "falta_elegir_transporte":
        wa_procesar_eleccion_transporte(pedido, texto)
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
            statuses = value.get("statuses") or []
            messages = value.get("messages") or []

            # Estados de entrega/lectura de mensajes salientes (sent/delivered/read/failed).
            # Esto alimenta las tildes del chat interno del pedido.
            if statuses:
                _procesar_statuses_whatsapp(statuses)

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
                    try:
                        from app import registrar_whatsapp_mensaje
                        registrar_whatsapp_mensaje(
                            pedido=pedido,
                            telefono=telefono,
                            direccion="in",
                            autor="cliente",
                            texto=texto,
                            message_id_meta=msg.get("id", ""),
                            estado="recibido",
                        )
                    except Exception as e:
                        print("[WA-HIST] Error registrando entrada:", e)
                    _routear_mensaje(pedido, texto, telefono)

        except Exception as e:
            print("[WA] Error procesando webhook:", e)

        # Meta requiere siempre 200
        return jsonify({"status": "ok"}), 200

    print("[WA] Webhook WhatsApp registrado en /webhook/whatsapp ✓")
