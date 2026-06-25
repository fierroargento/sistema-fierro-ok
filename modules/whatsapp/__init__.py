"""
modules/whatsapp/__init__.py
─────────────────────────────
Punto de entrada del módulo WhatsApp.

APB 2026-05:
- Este módulo registra SOLO el webhook.
- El scheduler periódico queda unificado en app.py vía APScheduler.
- No se registra before_request para evitar ejecuciones duplicadas, mensajes dobles
  o que el bot vuelva a escribir cuando un operador tomó la conversación.
"""

from .config import modulo_activo
from .webhook import registrar_webhook
from .general_routes import registrar_wa_general_routes
from .flows import (
    wa_enviar_confirmacion_sucursal,
    wa_enviar_solicitud_datos,
    wa_enviar_numero_seguimiento,
    wa_enviar_listo_para_retirar,
    wa_enviar_postventa,
)
from .scheduler import ejecutar_timers


def activar(app):
    """Activa el webhook si WhatsApp está configurado.

    El scheduler NO se engancha acá. Queda centralizado en app.py para que haya
    un único motor periódico en Render.
    """
    registrar_wa_general_routes(app)

    if not modulo_activo():
        print("[WA] Módulo WhatsApp en standby — configurar .env para activar")
        return

    registrar_webhook(app)
    print("[WA] Módulo WhatsApp activo ✓")


__all__ = [
    "activar",
    "registrar_wa_general_routes",
    "ejecutar_timers",
    "wa_enviar_confirmacion_sucursal",
    "wa_enviar_solicitud_datos",
    "wa_enviar_numero_seguimiento",
    "wa_enviar_listo_para_retirar",
    "wa_enviar_postventa",
]
