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
    send_file,
    session,
    url_for,
)

from services.inventario_admin import (
    procesar_accion_inventario_admin,
)
from services.inventario_consultas import (
    obtener_datos_panel_inventario,
)
from services.inventario_conteos_excel import (
    crear_plantilla_conteo,
    importar_conteo_excel,
    obtener_conteo_tenant,
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
            abrir_configuracion=(
                request.args.get("panel")
                == "configuracion"
            ),
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
        panel_destino = (
            request.form.get("panel_destino")
            or "operaciones-inventario"
        ).strip()
        if panel_destino not in {
            "configuracion-inventario",
            "operaciones-inventario",
            "existencias-inventario",
            "conteos-inventario",
            "automatizacion-pedidos",
            "politicas-disponibilidad",
        }:
            panel_destino = "operaciones-inventario"
        parametros_retorno = {}
        if panel_destino == "configuracion-inventario":
            parametros_retorno["panel"] = "configuracion"

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
                _anchor=panel_destino,
                **parametros_retorno,
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
                _anchor=panel_destino,
                **parametros_retorno,
            ))

    @blueprint.route("/admin/inventario/conteos/<int:conteo_id>/plantilla")
    @login_required
    def descargar_plantilla_conteo(conteo_id):
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        conteo = obtener_conteo_tenant(
            conteo_id, organizacion.id, modelos=modelos,
        )
        if conteo is None:
            return redirect(url_for(
                "admin_inventario.panel",
                error="No se encontró el inventario solicitado.",
                _anchor="conteos-inventario",
            ))
        return send_file(
            crear_plantilla_conteo(conteo),
            as_attachment=True,
            download_name=f"conteo-inventario-{conteo.id}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @blueprint.route(
        "/admin/inventario/conteos/<int:conteo_id>/importar",
        methods=["POST"],
    )
    @login_required
    def importar_plantilla_conteo(conteo_id):
        usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        conteo = obtener_conteo_tenant(
            conteo_id, organizacion.id, modelos=modelos,
        )
        try:
            if conteo is None:
                raise ValueError("No se encontró el inventario solicitado.")
            archivo = request.files.get("archivo_conteo")
            if archivo is None or not archivo.filename:
                raise ValueError("Seleccioná la plantilla XLSX completa.")
            filas = importar_conteo_excel(conteo, archivo, db_session=db.session)
            registrar_auditoria(
                "Importó conteo físico",
                entidad="conteo_inventario",
                entidad_id=conteo.id,
                detalle=f"Inventario {conteo.codigo}; filas: {filas}; usuario: {getattr(usuario, 'username', 'admin')}",
            )
            return redirect(url_for(
                "admin_inventario.panel",
                ok=f"Conteo {conteo.codigo} importado: {filas} SKU listos para revisar.",
                _anchor="conteos-inventario",
            ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_inventario.panel",
                error=str(error),
                _anchor="conteos-inventario",
            ))

    return blueprint
