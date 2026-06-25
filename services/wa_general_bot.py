"""
services/wa_general_bot.py

Reglas iniciales para mensajes de WhatsApp sin pedido activo.

Objetivo:
- Agradecimientos: responder automatico.
- Clientes con historial: escalar a operador.
- Contactos nuevos: ofrecer menu inicial.
"""

import re
import unicodedata

from services.telefonos import normalizar_telefono_service
from services.wa_general import obtener_pedidos_por_telefono


ACCION_AGRADECIMIENTO = "agradecimiento"
ACCION_MENU_CONTACTO_NUEVO = "menu_contacto_nuevo"
ACCION_ESCALAR_OPERADOR = "escalar_operador"
ACCION_SIN_TELEFONO = "sin_telefono"


PALABRAS_AGRADECIMIENTO = [
    "gracias",
    "muchas gracias",
    "mil gracias",
    "excelente",
    "genial",
    "buenisimo",
    "buenisima",
    "muy bueno",
    "muy buena",
    "me encanto",
    "me encanta",
    "quedo hermoso",
    "quedo hermosa",
    "llego bien",
    "todo bien",
    "los recomiendo",
    "lo recomiendo",
    "voy a recomendar",
    "recomendar",
    "super contenta",
    "super contento",
    "feliz",
]

PALABRAS_PROBLEMA = [
    "pero",
    "problema",
    "reclamo",
    "roto",
    "rota",
    "rompio",
    "fallo",
    "falla",
    "fallado",
    "fallada",
    "mal",
    "demora",
    "no llego",
    "no me llego",
    "no anda",
    "equivocado",
    "equivocada",
    "devolucion",
    "cambio",
]


def normalizar_texto_wa_general(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def es_opcion_menu_wa_general(texto):
    texto_norm = normalizar_texto_wa_general(texto)
    return bool(re.fullmatch(r"(opcion\s*)?[1-4]", texto_norm))


def es_agradecimiento_wa_general(texto):
    texto_norm = normalizar_texto_wa_general(texto)

    if not texto_norm:
        return False

    if any(palabra in texto_norm for palabra in PALABRAS_PROBLEMA):
        return False

    return any(palabra in texto_norm for palabra in PALABRAS_AGRADECIMIENTO)


def respuesta_agradecimiento_wa_general():
    return (
        "\u00a1Hola! Qu\u00e9 alegr\u00eda leer eso \U0001f60a\n"
        "Much\u00edsimas gracias por tu mensaje y por recomendarnos. "
        "Nos ayuda un mont\u00f3n.\n"
        "\u00a1Que disfrutes mucho la parrilla! \U0001f525"
    )


def respuesta_menu_contacto_nuevo_wa_general():
    return (
        "\u00a1Hola! \U0001f44b Somos Fierro 100% Argento.\n"
        "Para ayudarte, respond\u00e9 con una opci\u00f3n:\n\n"
        "1) Quiero comprar o ver productos\n"
        "2) Consultar por un pedido o env\u00edo\n"
        "3) Postventa o problema con una compra\n"
        "4) Hablar con un operador"
    )


def telefono_tiene_historial_pedidos_wa_general(telefono, Pedido):
    if Pedido is None:
        return False

    try:
        return bool(obtener_pedidos_por_telefono(telefono, Pedido))
    except Exception:
        return False


def telefono_tiene_historial_whatsapp_wa_general(
    telefono,
    WhatsAppMensaje,
    limite=50,
):
    if WhatsAppMensaje is None:
        return False

    tel = normalizar_telefono_service(telefono)
    if not tel:
        return False

    try:
        mensajes = (
            WhatsAppMensaje.query
            .filter(WhatsAppMensaje.telefono.isnot(None))
            .order_by(WhatsAppMensaje.fecha.desc())
            .limit(limite)
            .all()
        )
    except Exception:
        return False

    cantidad = 0

    for mensaje in mensajes:
        tel_mensaje = normalizar_telefono_service(
            getattr(mensaje, "telefono", "")
        )

        if tel_mensaje != tel:
            continue

        cantidad += 1

        # Si el webhook ya guardo el mensaje entrante actual, cantidad 1
        # puede ser solo el mensaje que estamos procesando. Con mas de 1
        # ya no lo tratamos como contacto nuevo de cero.
        if cantidad > 1:
            return True

    return False


def clasificar_sin_pedido_activo_wa_general(
    texto,
    tiene_historial_pedidos=False,
    tiene_historial_whatsapp=False,
):
    if es_agradecimiento_wa_general(texto):
        return ACCION_AGRADECIMIENTO

    if tiene_historial_pedidos:
        return ACCION_ESCALAR_OPERADOR

    if tiene_historial_whatsapp:
        return ACCION_ESCALAR_OPERADOR

    if es_opcion_menu_wa_general(texto):
        return ACCION_ESCALAR_OPERADOR

    return ACCION_MENU_CONTACTO_NUEVO


def manejar_sin_pedido_activo_wa_general(
    texto,
    telefono,
    Pedido,
    WhatsAppMensaje,
    wa_enviar_texto,
):
    tel = normalizar_telefono_service(telefono)

    if not tel:
        return ACCION_SIN_TELEFONO

    tiene_historial_pedidos = telefono_tiene_historial_pedidos_wa_general(
        tel,
        Pedido,
    )
    tiene_historial_whatsapp = telefono_tiene_historial_whatsapp_wa_general(
        tel,
        WhatsAppMensaje,
    )

    accion = clasificar_sin_pedido_activo_wa_general(
        texto,
        tiene_historial_pedidos=tiene_historial_pedidos,
        tiene_historial_whatsapp=tiene_historial_whatsapp,
    )

    if accion == ACCION_AGRADECIMIENTO:
        wa_enviar_texto(
            tel,
            respuesta_agradecimiento_wa_general(),
        )
        return accion

    if accion == ACCION_MENU_CONTACTO_NUEVO:
        wa_enviar_texto(
            tel,
            respuesta_menu_contacto_nuevo_wa_general(),
        )
        return accion

    return accion
