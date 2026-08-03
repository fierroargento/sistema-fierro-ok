"""
Blueprint tenant de estructura empresarial.

Las rutas resuelven la membresia autorizada y delegan
consultas y operaciones a servicios sin Flask.
"""

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.estructura_admin import (
    procesar_accion_estructura_admin,
)
from services.estructura_consultas import (
    obtener_datos_panel_estructura,
)
from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


def crear_blueprint_estructura(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_estructura",
        __name__,
    )

    login_required = dependencias[
        "login_required"
    ]
    usuario_actual = dependencias[
        "usuario_actual"
    ]
    registrar_auditoria = dependencias[
        "registrar_auditoria"
    ]
    db = dependencias["db"]
    UsuarioOrganizacion = dependencias[
        "UsuarioOrganizacion"
    ]
    modelos = dependencias["modelos"]

    def resolver_acceso():
        usuario = usuario_actual()

        try:
            membresia = resolver_tenant_usuario(
                usuario,
                UsuarioOrganizacion=(
                    UsuarioOrganizacion
                ),
                organizacion_id=session.get(
                    "organizacion_id"
                ),
            )
        except TenantError as error:
            return None, None, redirect(url_for(
                "inicio",
                error=str(error),
            ))

        if membresia.rol != "admin":
            return None, None, redirect(url_for(
                "inicio"
            ))

        session["organizacion_id"] = (
            membresia.organizacion_id
        )

        return (
            usuario,
            membresia.organizacion,
            None,
        )

    @blueprint.route("/admin/estructura")
    @login_required
    def panel():
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        datos = obtener_datos_panel_estructura(
            organizacion.id,
            modelos=modelos,
        )

        return render_template(
            "admin_estructura.html",
            organizacion=organizacion,
            **datos,
            ok_feedback=(
                request.args.get("ok")
                or ""
            ).strip(),
            error=(
                request.args.get("error")
                or ""
            ).strip(),
        )

    @blueprint.route(
        "/admin/estructura/guardar",
        methods=["POST"],
    )
    @login_required
    def guardar():
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        accion = (
            request.form.get("accion")
            or ""
        ).strip()

        try:
            mensaje = (
                procesar_accion_estructura_admin(
                    accion,
                    request.form,
                    organizacion=organizacion,
                    modelos=modelos,
                    db_session=db.session,
                )
            )

            registrar_auditoria(
                "Configuro estructura empresarial",
                entidad="estructura_empresarial",
                entidad_id=organizacion.id,
                detalle=(
                    f"Accion: {accion}. {mensaje}"
                ),
            )

            return redirect(url_for(
                "admin_estructura.panel",
                ok=mensaje,
            ))

        except Exception as error:
            db.session.rollback()

            print(
                "[ESTRUCTURA ADMIN] "
                f"No se pudo ejecutar {accion}: "
                f"{error}"
            )

            return redirect(url_for(
                "admin_estructura.panel",
                error=str(error),
            ))

    return blueprint
