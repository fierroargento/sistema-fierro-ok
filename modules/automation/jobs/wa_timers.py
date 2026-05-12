"""
Job automático WhatsApp timers.

Extraído desde app.py sin cambiar lógica.
"""

def ejecutar_job_wa_timers(app, db):
    """Ejecuta timers de WhatsApp cada 5 minutos."""

    try:
        with app.app_context():
            from modules.whatsapp.scheduler import ejecutar_timers

            ejecutar_timers()

    except Exception as e:
        print("[SCHEDULER WA] Error:", e)

        try:
            db.session.rollback()
        except Exception:
            pass

    finally:
        try:
            db.session.remove()
        except Exception:
            pass