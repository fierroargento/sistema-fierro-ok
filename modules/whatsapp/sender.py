"""
modules/whatsapp/sender.py
──────────────────────────
Funciones de bajo nivel para enviar mensajes por WhatsApp Business API.
Soporta texto, imagen y texto+imagen.

APB conversación interna:
- Todo envío intenta registrar historial en whatsapp_mensaje.
- Si falla el registro, NO bloquea el envío.
"""

import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .config import WA_TOKEN, WA_API_URL


def _registrar_historial(pedido=None, telefono="", texto="", autor="bot", estado="", error="", message_id_meta=""):
    try:
        from app import registrar_whatsapp_mensaje
        registrar_whatsapp_mensaje(
            pedido=pedido,
            telefono=telefono,
            direccion="out",
            autor=autor,
            texto=texto,
            message_id_meta=message_id_meta,
            estado=estado,
            error=error,
        )
    except Exception as e:
        print("[WA-HIST] Error registrando salida:", e)


def _wa_post(payload):
    """Envía un payload a la API de Meta. Devuelve (ok, data/error)."""
    if not WA_TOKEN:
        msg = "WHATSAPP_TOKEN no configurado — módulo inactivo"
        print("[WA]", msg)
        return False, msg

    req = Request(
        WA_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WA_TOKEN}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[WA] Enviado a {payload.get('to')}: {data}")
            return True, data
    except HTTPError as e:
        detalle = e.read().decode()
        print(f"[WA] Error HTTP {e.code}:", detalle)
        return False, detalle
    except Exception as e:
        print(f"[WA] Error:", e)
        return False, str(e)


def _extraer_message_id(data):
    try:
        messages = (data or {}).get("messages") or []
        if messages:
            return messages[0].get("id") or ""
    except Exception:
        pass
    return ""


def wa_enviar_texto(telefono, texto, pedido=None, autor="bot", registrar=True):
    """Envía un mensaje de texto simple."""
    telefono = re.sub(r"\D", "", str(telefono or ""))
    texto_limpio = str(texto or "").strip()
    if not telefono or not texto_limpio:
        if registrar:
            _registrar_historial(pedido, telefono, texto_limpio, autor=autor, estado="error", error="Falta teléfono o texto")
        return False

    ok, data = _wa_post({
        "messaging_product": "whatsapp",
        "to":   telefono,
        "type": "text",
        "text": {"body": texto_limpio},
    })

    if registrar:
        _registrar_historial(
            pedido=pedido,
            telefono=telefono,
            texto=texto_limpio,
            autor=autor,
            estado="enviado" if ok else "error",
            error="" if ok else str(data),
            message_id_meta=_extraer_message_id(data) if ok else "",
        )
    return ok


def wa_enviar_imagen(telefono, imagen_url, caption="", pedido=None, autor="bot", registrar=True):
    """Envía una imagen con caption opcional."""
    telefono = re.sub(r"\D", "", str(telefono or ""))
    if not telefono or not imagen_url:
        if registrar:
            _registrar_historial(pedido, telefono, caption, autor=autor, estado="error", error="Falta teléfono o imagen")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to":    telefono,
        "type":  "image",
        "image": {"link": imagen_url},
    }
    if caption:
        payload["image"]["caption"] = str(caption).strip()

    ok, data = _wa_post(payload)
    if registrar:
        texto_hist = caption or f"[Imagen] {imagen_url}"
        _registrar_historial(
            pedido=pedido,
            telefono=telefono,
            texto=texto_hist,
            autor=autor,
            estado="enviado" if ok else "error",
            error="" if ok else str(data),
            message_id_meta=_extraer_message_id(data) if ok else "",
        )
    return ok


def wa_enviar_producto(telefono, texto, imagen_url="", pedido=None, autor="bot"):
    """
    Envía descripción de un producto.
    Si tiene imagen_url la manda como imagen con el texto de caption.
    Si no tiene imagen manda solo texto.
    """
    if imagen_url:
        return wa_enviar_imagen(telefono, imagen_url, caption=texto, pedido=pedido, autor=autor)
    return wa_enviar_texto(telefono, texto, pedido=pedido, autor=autor)
