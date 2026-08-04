"""
Administración del maestro logístico de productos.

Producto continúa siendo una identidad global de plataforma.
Los catálogos comerciales pertenecientes a cada tenant se
administran mediante Catalogo y CatalogoProducto.
"""

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.productos_admin import (
    procesar_accion_productos_plataforma,
)
from services.productos_consultas import (
    obtener_panel_productos_plataforma,
)
from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


SLUG_ORGANIZACION_PLATAFORMA = "grupo-fierro"


def _es_organizacion_plataforma(
    organizacion,
):
    return (
        getattr(
            organizacion,
            "slug",
            None,
        )
        == SLUG_ORGANIZACION_PLATAFORMA
    )


def crear_blueprint_productos(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_productos",
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
    Producto = dependencias["Producto"]
    sincronizar_excel = dependencias[
        "sincronizar_excel"
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
            return None, None, redirect(
                url_for(
                    "inicio",
                    error=str(error),
                )
            )

        organizacion = membresia.organizacion

        if membresia.rol != "admin":
            return None, None, redirect(
                url_for("inicio")
            )

        if not _es_organizacion_plataforma(
            organizacion
        ):
            return None, None, redirect(
                url_for(
                    "inicio",
                    error=(
                        "El catálogo maestro de "
                        "productos es exclusivo "
                        "de la plataforma."
                    ),
                )
            )

        session["organizacion_id"] = (
            membresia.organizacion_id
        )

        return usuario, organizacion, None

    @blueprint.route(
        "/admin/productos",
        methods=["GET", "POST"],
    )
    @login_required
    def panel():
        usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        mensaje = (
            request.args.get("ok")
            or ""
        ).strip()
        error = (
            request.args.get("error")
            or ""
        ).strip()
        filtro_sku = (
            request.args.get("sku")
            or ""
        ).strip()

        if request.method == "POST":
            accion = (
                request.form.get("accion")
                or "importar_excel"
            ).strip()

            try:
                mensaje, sku = (
                    procesar_accion_productos_plataforma(
                        accion,
                        request.form,
                        request.files,
                        Producto=Producto,
                        db=db,
                        sincronizar_excel=(
                            sincronizar_excel
                        ),
                    )
                )

                registrar_auditoria(
                    (
                        "Configuró catálogo "
                        "maestro de productos"
                    ),
                    entidad="producto",
                    entidad_id=organizacion.id,
                    detalle=(
                        f"Acción: {accion}. "
                        f"{mensaje}"
                    ),
                )

                argumentos = {
                    "ok": mensaje,
                }

                if sku:
                    argumentos["sku"] = sku

                return redirect(
                    url_for(
                        "admin_productos.panel",
                        **argumentos,
                    )
                )

            except Exception as error_accion:
                db.session.rollback()

                print(
                    "[PRODUCTOS ADMIN] "
                    f"No se pudo ejecutar "
                    f"{accion}: "
                    f"{error_accion}"
                )

                error = str(error_accion)

        datos = (
            obtener_panel_productos_plataforma(
                Producto,
                filtro_sku=filtro_sku,
            )
        )

        return render_template(
            "admin_productos.html",
            mensaje=mensaje,
            error=error,
            **datos,
        )

    return blueprint
