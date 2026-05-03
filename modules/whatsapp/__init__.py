"""
modules/whatsapp/__init__.py
─────────────────────────────
Punto de entrada del módulo WhatsApp.

Para activar el módulo, agregar al .env:
    WHATSAPP_TOKEN=...
    WHATSAPP_PHONE_NUMBER_ID=...
    WHATSAPP_VERIFY_TOKEN=...

Y descomentar en app.py (al final del bloque with app.app_context()):
    from modules.whatsapp import activar
    activar(app)
"""

from .config import modulo_activo
from .webhook import registrar_webhook
from .flows import (
    wa_enviar_confirmacion_sucursal,
    wa_enviar_solicitud_datos,
    wa_enviar_numero_seguimiento,
    wa_enviar_listo_para_retirar,
    wa_enviar_postventa,
)
from .scheduler import ejecutar_timers


def activar(app):
    """
    Activa el módulo WhatsApp registrando el webhook en la app Flask.
    Solo hace algo si las credenciales están configuradas en el .env.
    """
    if not modulo_activo():
        print("[WA] Módulo WhatsApp en standby — configurar .env para activar")
        return

    registrar_webhook(app)
    print("[WA] Módulo WhatsApp activo ✓")


__all__ = [
    "activar",
    "ejecutar_timers",
    "wa_enviar_confirmacion_sucursal",
    "wa_enviar_solicitud_datos",
    "wa_enviar_numero_seguimiento",
    "wa_enviar_listo_para_retirar",
    "wa_enviar_postventa",
]
