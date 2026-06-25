"""
modules/whatsapp/general_routes.py

Rutas de WhatsApp General.

Regla:
- No mezclar WhatsApp operativo de pedidos activos con atencion general.
- Esta pantalla muestra contactos nuevos o clientes cuyo pedido ya no esta activo.
"""

from flask import jsonify, redirect, render_template, request, url_for
from services.wa_general import (
    armar_conversaciones_wa_general,
    contar_no_leidos_wa_general,
    mensaje_esta_no_leido_wa_general,
    mensaje_visible_en_chat_wa_general,
    normalizar_telefono_simple,
)


def registrar_wa_general_routes(app):
    """Registra rutas web de la bandeja WhatsApp General."""
    from app import login_required

    @app.context_processor
    def wa_general_badge_context():
        """
        Expone wa_general_no_leidos para mostrar badge en Inicio.

        Se calcula solo para admin/carga y solo en pantallas que usan index.html,
        para no cargar consultas innecesarias en todo el sistema.
        """
        try:
            from app import Pedido, WhatsAppMensaje, rol_actual

            if rol_actual() not in ["admin", "carga"]:
                return {"wa_general_no_leidos": 0}

            if request.endpoint not in {"inicio", "pedidos_preparacion"}:
                return {"wa_general_no_leidos": 0}

            return {
                "wa_general_no_leidos": contar_no_leidos_wa_general(
                    WhatsAppMensaje,
                    Pedido,
                    limite=500,
                )
            }
        except Exception:
            return {"wa_general_no_leidos": 0}

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

                if tel_mensaje != conversacion_seleccionada.telefono:
                    continue

                if not mensaje_visible_en_chat_wa_general(mensaje, Pedido):
                    continue

                mensajes.append(mensaje)

            mensajes = list(reversed(mensajes[-120:]))

        return render_template(
            "wa_general.html",
            conversaciones=conversaciones,
            conversacion_seleccionada=conversacion_seleccionada,
            telefono_seleccionado=telefono_seleccionado,
            mensajes=mensajes,
        )

    @app.route("/wa-general/marcar-leido", methods=["POST"])
    @login_required
    def wa_general_marcar_leido():
        from app import Pedido, WhatsAppMensaje, db, rol_actual

        if rol_actual() not in ["admin", "carga"]:
            return jsonify({"ok": False, "error": "sin_permiso"}), 403

        payload = request.get_json(silent=True) or {}
        telefono = normalizar_telefono_simple(
            payload.get("telefono") or request.form.get("telefono") or ""
        )

        if not telefono:
            return jsonify({"ok": False, "error": "telefono_requerido"}), 400

        mensajes_candidatos = (
            WhatsAppMensaje.query
            .filter(WhatsAppMensaje.telefono.isnot(None))
            .order_by(WhatsAppMensaje.fecha.desc())
            .limit(1000)
            .all()
        )

        actualizados = 0

        for mensaje in mensajes_candidatos:
            tel_mensaje = normalizar_telefono_simple(
                getattr(mensaje, "telefono", "")
            )

            if tel_mensaje != telefono:
                continue

            if not mensaje_visible_en_chat_wa_general(mensaje, Pedido):
                continue

            if not mensaje_esta_no_leido_wa_general(mensaje):
                continue

            mensaje.estado = "leido"
            actualizados += 1

        if actualizados:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return jsonify({"ok": False, "error": "commit_error"}), 500

        return jsonify({"ok": True, "actualizados": actualizados})

    @app.route("/wa-general/enviar", methods=["POST"])
    @login_required
    def wa_general_enviar():
        from app import rol_actual
        from modules.whatsapp.sender import wa_enviar_texto

        if rol_actual() not in ["admin", "carga"]:
            return redirect(url_for("inicio"))

        telefono = normalizar_telefono_simple(request.form.get("telefono", ""))
        texto = (request.form.get("mensaje") or "").strip()

        if not telefono:
            return redirect(url_for("wa_general", error="Telefono requerido."))

        if not texto:
            return redirect(url_for(
                "wa_general",
                telefono=telefono,
                error="Escribi un mensaje antes de enviar.",
            ))

        ok = wa_enviar_texto(
            telefono,
            texto,
            pedido=None,
            autor="operador",
            registrar=True,
        )

        if ok:
            return redirect(url_for(
                "wa_general",
                telefono=telefono,
                ok="Mensaje enviado por WhatsApp.",
            ))

        return redirect(url_for(
            "wa_general",
            telefono=telefono,
            error="No se pudo enviar el mensaje. Si la ventana esta cerrada, envia el template de apertura.",
        ))

    @app.route("/wa-general/enviar-template-operador", methods=["POST"])
    @login_required
    def wa_general_enviar_template_operador():
        from app import rol_actual
        from modules.whatsapp.config import WA_TEMPLATE_INICIO_CHAT_OPERADOR
        from modules.whatsapp.sender import wa_enviar_template

        if rol_actual() not in ["admin", "carga"]:
            return redirect(url_for("inicio"))

        telefono = normalizar_telefono_simple(request.form.get("telefono", ""))
        nombre = (request.form.get("nombre") or "Cliente").strip().split()[0]
        referencia = "WA General"

        if not telefono:
            return redirect(url_for("wa_general", error="Telefono requerido."))

        ok = wa_enviar_template(
            telefono,
            WA_TEMPLATE_INICIO_CHAT_OPERADOR,
            parametros=[
                nombre or "Cliente",
                referencia,
            ],
            pedido=None,
            autor="operador",
            registrar=True,
        )

        if ok:
            return redirect(url_for(
                "wa_general",
                telefono=telefono,
                ok="Template de apertura enviado.",
            ))

        return redirect(url_for(
            "wa_general",
            telefono=telefono,
            error="No se pudo enviar el template de apertura.",
        ))

    @app.route("/wa-general/cerrar", methods=["POST"])
    @login_required
    def wa_general_cerrar():
        from app import Pedido, WhatsAppMensaje, db, rol_actual

        if rol_actual() not in ["admin", "carga"]:
            return redirect(url_for("inicio"))

        telefono = normalizar_telefono_simple(request.form.get("telefono", ""))

        if not telefono:
            return redirect(url_for("wa_general"))

        mensajes_candidatos = (
            WhatsAppMensaje.query
            .filter(WhatsAppMensaje.telefono.isnot(None))
            .order_by(WhatsAppMensaje.fecha.desc())
            .limit(1000)
            .all()
        )

        actualizados = 0

        for mensaje in mensajes_candidatos:
            tel_mensaje = normalizar_telefono_simple(
                getattr(mensaje, "telefono", "")
            )

            if tel_mensaje != telefono:
                continue

            if not mensaje_visible_en_chat_wa_general(mensaje, Pedido):
                continue

            if not mensaje_esta_no_leido_wa_general(mensaje):
                continue

            mensaje.estado = "leido"
            actualizados += 1

        if actualizados:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return redirect(url_for(
                    "wa_general",
                    telefono=telefono,
                    error="No se pudo cerrar la conversacion.",
                ))

        return redirect(url_for(
            "wa_general",
            ok="Conversacion cerrada.",
        ))
