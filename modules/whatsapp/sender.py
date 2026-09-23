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
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from services.logger import get_app_logger
from services.busqueda_pedidos import buscar_pedido_activo_por_telefono
from .runtime import (
    ia_marcar_mensaje_bot,
    ia_puede_enviar_automatico,
    registrar_whatsapp_mensaje,
    wa_ventana_24h_abierta,
)
from services.whatsapp_template_params import sanitizar_parametros_template_meta
from services.seguridad_entorno import (
    conexiones_externas_habilitadas,
    efectos_externos_habilitados,
)
from services.whatsapp_salida_tenant import (
    ConfiguracionSalidaWhatsAppError,
    resolver_configuracion_salida_whatsapp,
)

logger = get_app_logger(__name__)


def _registrar_historial(pedido=None, telefono="", texto="", autor="bot", estado="", error="", message_id_meta=""):
    try:
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


def _identidad_tenant_salida(pedido=None, organizacion_id=None, unidad_negocio_id=None):
    organizacion_id = organizacion_id or getattr(pedido, "organizacion_id", None)
    unidad_negocio_id = unidad_negocio_id or getattr(pedido, "unidad_negocio_id", None)
    try:
        organizacion_id = int(organizacion_id)
        unidad_negocio_id = int(unidad_negocio_id)
    except (TypeError, ValueError) as error:
        raise ConfiguracionSalidaWhatsAppError(
            "Salida WhatsApp bloqueada: falta identidad de organización/unidad."
        ) from error
    if organizacion_id <= 0 or unidad_negocio_id <= 0:
        raise ConfiguracionSalidaWhatsAppError(
            "Salida WhatsApp bloqueada: identidad de organización/unidad inválida."
        )
    return organizacion_id, unidad_negocio_id


def _resolver_configuracion_envio(
    *, pedido=None, organizacion_id=None, unidad_negocio_id=None,
):
    organizacion_id, unidad_negocio_id = _identidad_tenant_salida(
        pedido, organizacion_id, unidad_negocio_id,
    )
    from models.vinculo_canal_comercial import VinculoCanalComercial

    vinculos = (
        VinculoCanalComercial.query
        .filter_by(
            canal="whatsapp",
            estado="activo",
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id,
        )
        .all()
    )
    return resolver_configuracion_salida_whatsapp(
        vinculos,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        environ=os.environ,
    )


def _wa_post(
    payload, *, pedido=None, organizacion_id=None, unidad_negocio_id=None,
):
    """Envia un payload a la API de Meta. Devuelve (ok, data/error)."""
    if not efectos_externos_habilitados("WHATSAPP"):
        msg = "Envio WhatsApp bloqueado: Sistema Fierro esta en modo desconectado"
        logger.warning("[WA-SEGURIDAD] %s", msg)
        return False, msg

    if not conexiones_externas_habilitadas("WHATSAPP"):
        msg = "Envio WhatsApp bloqueado: conexion externa no habilitada"
        logger.warning("[WA-SEGURIDAD] %s", msg)
        return False, msg

    try:
        configuracion = _resolver_configuracion_envio(
            pedido=pedido,
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id,
        )
    except ConfiguracionSalidaWhatsAppError as error:
        msg = str(error)
        logger.warning("[WA-TENANT] %s", msg)
        return False, msg
    except Exception:
        msg = "Salida WhatsApp bloqueada: no se pudo resolver la cuenta tenant."
        logger.exception("[WA-TENANT] %s", msg)
        return False, msg

    req = Request(
        configuracion.api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {configuracion.token}",
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
        try:
            detalle = e.read().decode("utf-8", errors="replace")
        except Exception:
            detalle = ""

        codigo = getattr(e, "code", "")
        payload_seguro = dict(payload or {})

        if "to" in payload_seguro:
            payload_seguro["to"] = "***"

        logger.error(
            "[WA] Error HTTP enviando mensaje. Codigo: %s | Respuesta Meta: %s | Payload: %s",
            codigo,
            detalle[:2000],
            json.dumps(payload_seguro, ensure_ascii=False)[:2000],
        )

        return False, detalle or f"HTTPError {codigo}"
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

def wa_enviar_template(
    telefono, template_name, parametros=None, pedido=None, autor="bot",
    registrar=True, organizacion_id=None, unidad_negocio_id=None,
):
    """Envia una plantilla aprobada de Meta WhatsApp.

    Sirve para iniciar/reabrir conversacion cuando la ventana de 24 hs esta cerrada.
    """
    from .config import WA_TEMPLATE_LANG

    telefono = re.sub(r"\D", "", str(telefono or ""))
    template_name = str(template_name or "").strip()
    parametros = sanitizar_parametros_template_meta(parametros or [])

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

    ok, data = _wa_post(
        payload,
        pedido=pedido,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )

    texto_hist = f"[Template] {template_name} | Params: {parametros}"

    if ok and autor == "bot" and pedido is not None:
        try:
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
    organizacion_id=None,
    unidad_negocio_id=None,
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
            pedido = buscar_pedido_activo_por_telefono(telefono)
        except Exception as e:
            logger.exception("[WA-APB] No se pudo resolver pedido para candado")

    if autor == "bot" and pedido is not None:
        try:

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
                        organizacion_id=organizacion_id,
                        unidad_negocio_id=unidad_negocio_id,
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

    ok, data = _wa_post(
        {
            "messaging_product": "whatsapp",
            "to": telefono,
            "type": "text",
            "text": {"body": texto_limpio},
        },
        pedido=pedido,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )

    if ok and autor == "bot" and pedido is not None:
        try:
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


def wa_enviar_imagen(
    telefono, imagen_url, caption="", pedido=None, autor="bot", registrar=True,
    organizacion_id=None, unidad_negocio_id=None,
):
    """Envia una imagen con caption opcional."""
    telefono = re.sub(r"\D", "", str(telefono or ""))
    if not telefono or not imagen_url:
        if registrar:
            _registrar_historial(pedido, telefono, caption, autor=autor, estado="error", error="Falta telefono o imagen")
        return False

    if pedido is None:
        try:
            pedido = buscar_pedido_activo_por_telefono(telefono)
        except Exception as e:
            logger.exception("[WA-APB] No se pudo resolver pedido para imagen")

    texto_control = caption or f"[Imagen enviada] {imagen_url}"
    if autor == "bot" and pedido is not None:
        try:
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

    ok, data = _wa_post(
        payload,
        pedido=pedido,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )
    if caption:
        texto_hist = f"[Imagen enviada] {caption}"
    else:
        texto_hist = f"[Imagen enviada] {imagen_url}"
    if ok and autor == "bot" and pedido is not None:
        try:
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
