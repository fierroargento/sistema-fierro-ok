"""
Blueprint administrativo de facturacion multi-CUIT.

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

from services.facturacion_admin import (
    procesar_accion_facturacion_admin,
)
from services.facturacion_consultas import (
    obtener_datos_panel_facturacion,
)
from services.certificacion_offline_facturacion import certificar_facturacion, exportar_certificacion
from services.importacion_borradores_fiscales import previsualizar_borradores, exportar_previsualizacion
import json
from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


def crear_blueprint_facturacion(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_facturacion",
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

    @blueprint.route("/admin/facturacion")
    @login_required
    def panel():
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        datos = obtener_datos_panel_facturacion(
            organizacion_id=organizacion.id,
            modelos=modelos,
        )

        return render_template(
            "admin_facturacion.html",
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
        "/admin/facturacion/guardar",
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
                procesar_accion_facturacion_admin(
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
                "Configuró facturación multi-CUIT",
                entidad="facturacion_config",
                entidad_id=organizacion.id,
                detalle=(
                    f"Acción: {accion}. {mensaje}"
                ),
            )

            return redirect(url_for(
                "admin_facturacion.panel",
                ok=mensaje,
            ))

        except Exception as error:
            db.session.rollback()

            print(
                "[FACTURACION ADMIN] "
                f"No se pudo ejecutar {accion}: "
                f"{error}"
            )

            return redirect(url_for(
                "admin_facturacion.panel",
                error=str(error),
            ))

    @blueprint.route("/admin/facturacion/certificacion-offline", methods=["GET", "POST"])
    @login_required
    def certificacion_offline():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_datos_panel_facturacion(organizacion_id=organizacion.id, modelos=modelos)
        resultado = certificar_facturacion(
            organizacion_id=organizacion.id, modulo=datos["modulo_facturacion"],
            entidades=datos["entidades_fiscales"], configuraciones=datos["configuraciones"],
            puntos=datos["puntos_venta"], tipos=datos["tipos_comprobante"],
            borradores=datos["borradores"], eventos=datos["eventos"],
        )
        if request.method == "POST":
            return send_file(
                exportar_certificacion(resultado), as_attachment=True,
                download_name="certificacion_facturacion_offline.json", mimetype="application/json",
            )
        return render_template("admin_certificacion_facturacion_offline.html", certificacion=resultado)

    @blueprint.route("/admin/facturacion/importacion-offline", methods=["GET", "POST"])
    @login_required
    def importacion_offline():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        vista = None; error = ""
        if request.method == "POST":
            try:
                datos = obtener_datos_panel_facturacion(organizacion_id=organizacion.id, modelos=modelos)
                archivo = request.files.get("archivo")
                if archivo is None or not archivo.filename:
                    raise ValueError("Seleccioná un archivo CSV.")
                vista = previsualizar_borradores(
                    archivo.read(), organizacion_id=organizacion.id,
                    entidades=datos["entidades_fiscales"], puntos=datos["puntos_venta"],
                    tipos=datos["tipos_comprobante"],
                    referencias_existentes=[b.referencia_externa for b in datos["borradores"]],
                )
            except Exception as exc:
                error = str(exc)
        return render_template("admin_importacion_borradores_fiscales.html", vista=vista, error=error)

    @blueprint.route("/admin/facturacion/importacion-offline/exportar", methods=["POST"])
    @login_required
    def exportar_importacion_offline():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        resultado = json.loads(request.form.get("documento") or "{}")
        if resultado.get("organizacion_id") != organizacion.id or resultado.get("emision_real") is not False:
            return redirect(url_for("admin_facturacion.importacion_offline", error="El diagnóstico no pertenece al tenant."))
        return send_file(exportar_previsualizacion(resultado), as_attachment=True, download_name="previsualizacion_borradores_fiscales.json", mimetype="application/json")

    return blueprint
