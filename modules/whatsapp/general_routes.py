"""
modules/whatsapp/general_routes.py

Rutas de WhatsApp General.

Regla:
- No mezclar WhatsApp operativo de pedidos activos con atencion general.
- Esta pantalla muestra contactos nuevos o clientes cuyo pedido ya no esta activo.
"""

from flask import redirect, render_template, request, url_for
from services.wa_general import (
    armar_conversaciones_wa_general,
    normalizar_telefono_simple,
)


def registrar_wa_general_routes(app):
    """Registra rutas web de la bandeja WhatsApp General."""
    from app import login_required

    @app.route("/wa-general")
    @login_required
    def wa_general():
        from app import Pedido, WhatsAppMensaje, rol_actual

        if rol_actual() not in ["admin", "carga"]:
            return redirect(url_for("inicio"))

        telefono_seleccionado = normalizar_telefono_simple(
            request.args.get("telefono", "")
        )

        conversaciones = armar_conversaciones_wa_general(
            WhatsAppMensaje,
            Pedido,
            limite=80,
        )

        conversacion_seleccionada = None
        for conversacion in conversaciones:
            if (
                telefono_seleccionado
                and conversacion.telefono == telefono_seleccionado
            ):
                conversacion_seleccionada = conversacion
                break

        mensajes = []
        if conversacion_seleccionada:
            mensajes_candidatos = (
                WhatsAppMensaje.query
                .filter(WhatsAppMensaje.telefono.isnot(None))
                .order_by(WhatsAppMensaje.fecha.desc())
                .limit(1000)
                .all()
            )

            for mensaje in mensajes_candidatos:
                tel_mensaje = normalizar_telefono_simple(
                    getattr(mensaje, "telefono", "")
                )
                if tel_mensaje == conversacion_seleccionada.telefono:
                    mensajes.append(mensaje)

            mensajes = list(reversed(mensajes[-120:]))

        return render_template(
            "wa_general.html",
            conversaciones=conversaciones,
            conversacion_seleccionada=conversacion_seleccionada,
            telefono_seleccionado=telefono_seleccionado,
            mensajes=mensajes,
        )
