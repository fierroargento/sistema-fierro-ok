"""
modules/whatsapp/__init__.py
─────────────────────────────
Punto de entrada del módulo WhatsApp.
"""

from datetime import datetime, timedelta

from .config import modulo_activo, SCHEDULER_INTERVALO_SEGUNDOS
from .webhook import registrar_webhook
from .flows import (
    wa_enviar_confirmacion_sucursal,
    wa_enviar_solicitud_datos,
    wa_enviar_numero_seguimiento,
    wa_enviar_listo_para_retirar,
    wa_enviar_postventa,
)
from .scheduler import ejecutar_timers

_ultimo_scheduler = None
_scheduler_corriendo = False


def _registrar_scheduler_liviano(app):
    """Ejecuta scheduler cada N segundos enganchado a requests.

    Evita threads/background workers para no complicar Render ni romper deploy.
    """
    global _ultimo_scheduler, _scheduler_corriendo

    @app.before_request
    def _wa_scheduler_tick():
        global _ultimo_scheduler, _scheduler_corriendo
        ahora = datetime.utcnow()
        if _scheduler_corriendo:
            return
        if _ultimo_scheduler and (ahora - _ultimo_scheduler).total_seconds() < SCHEDULER_INTERVALO_SEGUNDOS:
            return
        _scheduler_corriendo = True
        try:
            ejecutar_timers()
            _ultimo_scheduler = ahora
        except Exception as e:
            print("[WA] Scheduler tick error:", e)
            try:
                from app import db
                db.session.rollback()
            except Exception:
                pass
        finally:
            try:
                from app import db
                db.session.remove()
            except Exception:
                pass
            _scheduler_corriendo = False


def activar(app):
    """Activa webhook y scheduler liviano si WhatsApp está configurado."""
    if not modulo_activo():
        print("[WA] Módulo WhatsApp en standby — configurar .env para activar")
        return

    registrar_webhook(app)
    _registrar_scheduler_liviano(app)
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
