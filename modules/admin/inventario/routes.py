"""
Blueprint administrativo de inventario multisucursal.

Las rutas resuelven el tenant autorizado y delegan
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

from services.inventario_admin import (
    procesar_accion_inventario_admin,
)
from services.inventario_consultas import (
    obtener_datos_panel_inventario,
)
from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


def crear_blueprint_inventario(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_inventario",
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

    @blueprint.route("/admin/inventario")
    @login_required
    def panel():
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        datos = obtener_datos_panel_inventario(
            organizacion,
            modelos=modelos,
        )

        return render_template(
            "admin_inventario.html",
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
        "/admin/inventario/guardar",
        methods=["POST"],
    )
    @login_required
    def guardar():
        usuario, organizacion, respuesta = (
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
                procesar_accion_inventario_admin(
                    accion,
                    request.form,
                    organizacion=organizacion,
                    modelos=modelos,
                    db_session=db.session,
                    usuario=(
                        getattr(
                            usuario,
                            "username",
                            None,
                        )
                        or "admin"
                    ),
                )
            )

            registrar_auditoria(
                "Configuró inventario interno",
                entidad="inventario",
                entidad_id=organizacion.id,
                detalle=(
                    f"Acción: {accion}. {mensaje}"
                ),
            )

            return redirect(url_for(
                "admin_inventario.panel",
                ok=mensaje,
            ))

        except Exception as error:
            db.session.rollback()

            print(
                "[INVENTARIO ADMIN] "
                f"No se pudo ejecutar {accion}: "
                f"{error}"
            )

            return redirect(url_for(
                "admin_inventario.panel",
                error=str(error),
            ))

    return blueprint
