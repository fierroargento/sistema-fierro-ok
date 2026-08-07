"""Blueprint del panel comercial tenant."""

from flask import Blueprint, redirect, render_template, request, session, url_for

from services.comercial_admin import procesar_accion_comercial
from services.comercial_consultas import obtener_datos_panel_comercial
from services.fuentes_costo_admin import (
    obtener_fuentes_costo,
    procesar_accion_fuente_costo,
)
from services.tenant_context import TenantError, resolver_tenant_usuario


def crear_blueprint_comercial(*, dependencias):
    blueprint = Blueprint("admin_comercial", __name__)
    db = dependencias["db"]
    modelos = dependencias["modelos"]

    def acceso():
        usuario = dependencias["usuario_actual"]()
        try:
            membresia = resolver_tenant_usuario(
                usuario,
                UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],
                organizacion_id=session.get("organizacion_id"),
            )
        except TenantError as error:
            return None, None, redirect(url_for("inicio", error=str(error)))
        if membresia.rol != "admin":
            return None, None, redirect(url_for("inicio"))
        session["organizacion_id"] = membresia.organizacion_id
        return usuario, membresia.organizacion, None

    @blueprint.route("/admin/comercial")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        return render_template(
            "admin_comercial.html", organizacion=organizacion,
            **obtener_datos_panel_comercial(organizacion.id, modelos=modelos),
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/guardar", methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        accion = (request.form.get("accion") or "").strip()
        try:
            mensaje = procesar_accion_comercial(
                accion, request.form, organizacion=organizacion,
                modelos=modelos, db_session=db.session, usuario=usuario,
            )
            dependencias["registrar_auditoria"](
                "Configuro administracion comercial",
                entidad="comercial", entidad_id=organizacion.id,
                detalle=f"Accion: {accion}. {mensaje}",
            )
            return redirect(url_for("admin_comercial.panel", ok=mensaje))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.panel", error=str(error)))

    @blueprint.route("/admin/comercial/fuentes-costos")
    @dependencias["login_required"]
    def fuentes_costos():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        return render_template(
            "admin_fuentes_costos.html",
            organizacion=organizacion,
            unidades=modelos["UnidadNegocio"].query.filter_by(
                organizacion_id=organizacion.id,
                activa=True,
            ).order_by(modelos["UnidadNegocio"].nombre).all(),
            **obtener_fuentes_costo(organizacion.id, modelos=modelos),
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route(
        "/admin/comercial/fuentes-costos/guardar",
        methods=["POST"],
    )
    @dependencias["login_required"]
    def guardar_fuente_costo():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        accion = (request.form.get("accion") or "").strip()
        try:
            mensaje = procesar_accion_fuente_costo(
                accion,
                request.form,
                organizacion=organizacion,
                modelos=modelos,
                db_session=db.session,
                usuario=usuario,
            )
            dependencias["registrar_auditoria"](
                "Configuro fuentes de costo productivo",
                entidad="fuente_costo",
                entidad_id=organizacion.id,
                detalle=f"Accion: {accion}. {mensaje}",
            )
            return redirect(url_for(
                "admin_comercial.fuentes_costos",
                ok=mensaje,
            ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_comercial.fuentes_costos",
                error=str(error),
            ))

    return blueprint
