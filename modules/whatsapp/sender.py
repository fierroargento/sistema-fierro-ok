"""
modules/whatsapp/sender.py
# ------------------------------------------------------------
Funciones de bajo nivel para enviar mensajes por WhatsApp Business API.
Soporta texto, imagen y texto+imagen.

APB conversacion interna:
- Todo envio intenta registrar historial en whatsapp_mensaje.
- Si falla el registro, NO bloquea el envio.
"""

import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .config import WA_TOKEN, WA_API_URL
from services.logger import get_app_logger

logger = get_app_logger(__name__)


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
        logger.exception("[WA-HIST] Error registrando salida")


def _wa_post(payload):
    """Envia un payload a la API de Meta. Devuelve (ok, data/error)."""
    if not WA_TOKEN:
        msg = "WHATSAPP_TOKEN no configurado -modulo inactivo"
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
        logger.exception(
    "[WA] Error HTTP enviando mensaje. Codigo: %s",
    getattr(e, "code", ""),
)
        return False, detalle
    except Exception as e:
        logger.exception("[WA] Error enviando mensaje")
        return False, str(e)


def _extraer_message_id(data):
    try:
        messages = (data or {}).get("messages") or []
        if messages:
            return messages[0].get("id") or ""
    except Exception:
        pass
    return ""

def wa_enviar_template(telefono, template_name, parametros=None, pedido=None, autor="bot", registrar=True):
    """Envia una plantilla aprobada de Meta WhatsApp.

    Sirve para iniciar/reabrir conversacion cuando la ventana de 24 hs esta cerrada.
    """
    from .config import WA_TEMPLATE_LANG

    telefono = re.sub(r"\D", "", str(telefono or ""))
    template_name = str(template_name or "").strip()
    parametros = parametros or []

    if not telefono or not template_name:
        if registrar:
            _registrar_historial(
                pedido,
                telefono,
                f"[Template] {template_name}",
                autor=autor,
                estado="error",
                error="Falta telefono o template_name",
            )
        return False

    components = []
    if parametros:
        components.append({
            "type": "body",
            "parameters": [
                {
                    "type": "text",
                    "text": str(valor or ""),
                }
                for valor in parametros
            ],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": WA_TEMPLATE_LANG,
            },
            "components": components,
        },
    }

    ok, data = _wa_post(payload)

    texto_hist = f"[Template] {template_name} | Params: {parametros}"

    if ok and autor == "bot" and pedido is not None:
        try:
            from app import ia_marcar_mensaje_bot
            ia_marcar_mensaje_bot(pedido, "whatsapp", texto_hist, commit=True)
        except Exception as e:
            logger.exception("[WA-APB] No se pudo marcar template bot")

    if registrar:
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

def wa_enviar_texto(
    telefono,
    texto,
    pedido=None,
    autor="bot",
    registrar=True,
    fallback_template=None,
    fallback_parametros=None,
):
    """Envia un mensaje de texto simple.

    APB anti-acoso:
    - si es bot automatico, no puede mandar 2 mensajes consecutivos sin respuesta;
    - respeta canal activo ML/WA;
    - bloquea duplicados.
    """
    telefono = re.sub(r"\D", "", str(telefono or ""))
    texto_limpio = str(texto or "").strip()
    if not telefono or not texto_limpio:
        if registrar:
            _registrar_historial(pedido, telefono, texto_limpio, autor=autor, estado="error", error="Falta telefono o texto")
        return False

    # Resolver pedido por telefono cuando el caller no lo pasa explicitamente.
    if pedido is None:
        try:
            from app import buscar_pedido_activo_por_telefono
            pedido = buscar_pedido_activo_por_telefono(telefono)
        except Exception as e:
            logger.exception("[WA-APB] No se pudo resolver pedido para candado")

    if autor == "bot" and pedido is not None:
        try:
            from app import ia_puede_enviar_automatico, wa_ventana_24h_abierta

            ventana_abierta = wa_ventana_24h_abierta(
                pedido=pedido,
                telefono=telefono,
            )

            if not ventana_abierta:
                motivo = "ventana_24h_cerrada"

                if fallback_template:
                    print(
                        f"[WA-APB] Ventana cerrada pedido "
                        f"#{getattr(pedido, 'id', '?')}: usando template {fallback_template}"
                    )

                    return wa_enviar_template(
                        telefono,
                        fallback_template,
                        parametros=fallback_parametros or [],
                        pedido=pedido,
                        autor=autor,
                        registrar=registrar,
                    )

                print(f"[WA-APB] Bloqueado envio automatico pedido #{getattr(pedido, 'id', '?')}: {motivo}")

                if registrar:
                    _registrar_historial(
                        pedido,
                        telefono,
                        texto_limpio,
                        autor=autor,
                        estado="bloqueado",
                        error=motivo,
                    )

                return False

            puede, motivo = ia_puede_enviar_automatico(
                pedido,
                "whatsapp",
                texto_limpio,
            )

            if not puede:
                print(f"[WA-APB] Bloqueado envio automatico pedido #{getattr(pedido, 'id', '?')}: {motivo}")

                if registrar:
                    _registrar_historial(
                        pedido,
                        telefono,
                        texto_limpio,
                        autor=autor,
                        estado="bloqueado",
                        error=motivo,
                    )

                return False

        except Exception as e:
            logger.exception("[WA-APB] Error evaluando candado")

    ok, data = _wa_post({
        "messaging_product": "whatsapp",
        "to":   telefono,
        "type": "text",
        "text": {"body": texto_limpio},
    })

    if ok and autor == "bot" and pedido is not None:
        try:
            from app import ia_marcar_mensaje_bot
            ia_marcar_mensaje_bot(pedido, "whatsapp", texto_limpio, commit=True)
        except Exception as e:
            print("[WA-APB] No se pudo marcar mensaje bot:", e)

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
    """Envia una imagen con caption opcional."""
    telefono = re.sub(r"\D", "", str(telefono or ""))
    if not telefono or not imagen_url:
        if registrar:
            _registrar_historial(pedido, telefono, caption, autor=autor, estado="error", error="Falta telefono o imagen")
        return False

    if pedido is None:
        try:
            from app import buscar_pedido_activo_por_telefono
            pedido = buscar_pedido_activo_por_telefono(telefono)
        except Exception as e:
            logger.exception("[WA-APB] No se pudo resolver pedido para imagen")

    texto_control = caption or f"[Imagen] {imagen_url}"
    if autor == "bot" and pedido is not None:
        try:
            from app import ia_puede_enviar_automatico
            puede, motivo = ia_puede_enviar_automatico(pedido, "whatsapp", texto_control)
            if not puede:
                print(f"[WA-APB] Bloqueado envio imagen pedido #{getattr(pedido, 'id', '?')}: {motivo}")
                if registrar:
                    _registrar_historial(pedido, telefono, texto_control, autor=autor, estado="bloqueado", error=motivo)
                return False
        except Exception as e:
            logger.exception("[WA-APB] Error evaluando candado imagen")

    payload = {
        "messaging_product": "whatsapp",
        "to":    telefono,
        "type":  "image",
        "image": {"link": imagen_url},
    }
    if caption:
        payload["image"]["caption"] = str(caption).strip()

    ok, data = _wa_post(payload)
    texto_hist = caption or f"[Imagen] {imagen_url}"
    if ok and autor == "bot" and pedido is not None:
        try:
            from app import ia_marcar_mensaje_bot
            ia_marcar_mensaje_bot(pedido, "whatsapp", texto_hist, commit=True)
        except Exception as e:
            print("[WA-APB] No se pudo marcar imagen bot:", e)
    if registrar:
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
    Envia descripcion de un producto.
    Si tiene imagen_url la manda como imagen con el texto de caption.
    Si no tiene imagen manda solo texto.
    """
    if imagen_url:
        return wa_enviar_imagen(telefono, imagen_url, caption=texto, pedido=pedido, autor=autor)
    return wa_enviar_texto(telefono, texto, pedido=pedido, autor=autor)

