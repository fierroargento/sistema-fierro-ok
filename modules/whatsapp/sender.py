"""
modules/whatsapp/sender.py
──────────────────────────
Funciones de bajo nivel para enviar mensajes por WhatsApp Business API.
Soporta texto, imagen y texto+imagen.
"""

import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .config import WA_TOKEN, WA_API_URL


def _wa_post(payload):
    """Envía un payload a la API de Meta. Devuelve True/False."""
    if not WA_TOKEN:
        print("[WA] WHATSAPP_TOKEN no configurado — módulo inactivo")
        return False

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
            return True
    except HTTPError as e:
        print(f"[WA] Error HTTP {e.code}:", e.read().decode())
        return False
    except Exception as e:
        print(f"[WA] Error:", e)
        return False


def wa_enviar_texto(telefono, texto):
    """Envía un mensaje de texto simple."""
    telefono = re.sub(r"\D", "", str(telefono or ""))
    if not telefono or not texto:
        return False

    return _wa_post({
        "messaging_product": "whatsapp",
        "to":   telefono,
        "type": "text",
        "text": {"body": str(texto).strip()},
    })


def wa_enviar_imagen(telefono, imagen_url, caption=""):
    """Envía una imagen con caption opcional."""
    telefono = re.sub(r"\D", "", str(telefono or ""))
    if not telefono or not imagen_url:
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to":    telefono,
        "type":  "image",
        "image": {"link": imagen_url},
    }
    if caption:
        payload["image"]["caption"] = str(caption).strip()

    return _wa_post(payload)


def wa_enviar_producto(telefono, texto, imagen_url=""):
    """
    Envía descripción de un producto.
    Si tiene imagen_url la manda como imagen con el texto de caption.
    Si no tiene imagen manda solo texto.
    """
    if imagen_url:
        return wa_enviar_imagen(telefono, imagen_url, caption=texto)
    return wa_enviar_texto(telefono, texto)
