"""
Blueprint administrativo de usuarios por organización.

La identidad autenticable es global, mientras que el rol y el
acceso operativo se administran mediante membresías tenant.
"""

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)
from services.usuarios_admin import (
    ROLES_TENANT,
    cambiar_estado_membresia_tenant,
    crear_usuario_tenant,
    editar_membresia_tenant,
)
from services.usuarios_consultas import (
    obtener_membresias_usuario,
)


def crear_blueprint_usuarios(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_usuarios",
        __name__,
    )

    db = dependencias["db"]
    login_required = dependencias[
        "login_required"
    ]
    usuario_actual = dependencias[
        "usuario_actual"
    ]
    registrar_auditoria = dependencias[
        "registrar_auditoria"
    ]
    UsuarioOrganizacion = dependencias[
        "UsuarioOrganizacion"
    ]
    UsuarioSistema = dependencias[
        "UsuarioSistema"
    ]

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

    def redireccion(
        *,
        ok=None,
        error=None,
    ):
        parametros = {}

        if ok:
            parametros["ok"] = ok

        if error:
            parametros["error"] = error

        return redirect(url_for(
            "admin_usuarios.panel",
            **parametros,
        ))

    @blueprint.route("/admin/usuarios")
    @login_required
    def panel():
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        membresias = obtener_membresias_usuario(
            organizacion_id=organizacion.id,
            UsuarioSistema=UsuarioSistema,
            UsuarioOrganizacion=(
                UsuarioOrganizacion
            ),
        )

        return render_template(
            "admin_usuarios.html",
            organizacion=organizacion,
            membresias=membresias,
            roles=ROLES_TENANT,
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
        "/admin/usuarios/nuevo",
        methods=["POST"],
    )
    @login_required
    def nuevo():
        usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        try:
            membresia, mensaje = (
                crear_usuario_tenant(
                    request.form,
                    organizacion=organizacion,
                    UsuarioSistema=UsuarioSistema,
                    UsuarioOrganizacion=(
                        UsuarioOrganizacion
                    ),
                    db_session=db.session,
                    creador=usuario,
                )
            )

            registrar_auditoria(
                "Creó usuario en organización",
                entidad="usuario_organizacion",
                entidad_id=membresia.id,
                detalle=(
                    f"Usuario "
                    f"{membresia.usuario.username}; "
                    f"rol {membresia.rol}."
                ),
            )

            return redireccion(ok=mensaje)

        except Exception as error:
            db.session.rollback()
            return redireccion(error=str(error))

    @blueprint.route(
        "/admin/usuarios/<int:id>/editar",
        methods=["POST"],
    )
    @login_required
    def editar(id):
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        try:
            membresia, mensaje = (
                editar_membresia_tenant(
                    id,
                    request.form,
                    organizacion=organizacion,
                    UsuarioOrganizacion=(
                        UsuarioOrganizacion
                    ),
                    db_session=db.session,
                )
            )

            registrar_auditoria(
                "Editó membresía de usuario",
                entidad="usuario_organizacion",
                entidad_id=membresia.id,
                detalle=(
                    f"Usuario "
                    f"{membresia.usuario.username}; "
                    f"rol {membresia.rol}."
                ),
            )

            return redireccion(ok=mensaje)

        except Exception as error:
            db.session.rollback()
            return redireccion(error=str(error))

    @blueprint.route(
        "/admin/usuarios/<int:id>/toggle",
        methods=["POST"],
    )
    @login_required
    def toggle(id):
        usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        try:
            membresia, mensaje = (
                cambiar_estado_membresia_tenant(
                    id,
                    organizacion=organizacion,
                    usuario_actual=usuario,
                    UsuarioOrganizacion=(
                        UsuarioOrganizacion
                    ),
                    db_session=db.session,
                )
            )

            registrar_auditoria(
                "Cambió acceso de usuario",
                entidad="usuario_organizacion",
                entidad_id=membresia.id,
                detalle=(
                    f"Usuario "
                    f"{membresia.usuario.username}; "
                    f"activa={membresia.activa}."
                ),
            )

            return redireccion(ok=mensaje)

        except Exception as error:
            db.session.rollback()
            return redireccion(error=str(error))

    return blueprint
