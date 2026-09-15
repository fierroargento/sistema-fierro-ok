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
from services.importacion_borradores_fiscales import previsualizar_borradores, exportar_previsualizacion, deserializar_previsualizacion, validar_confirmacion, confirmar_importacion, huellas_lotes_tenant
from services.gestion_lotes_fiscales import listar_lotes, obtener_lote, exportar_lote, anular_lote
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

    @blueprint.route("/admin/facturacion/importacion-offline/confirmar", methods=["POST"])
    @login_required
    def confirmar_importacion_offline():
        usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        try:
            datos = obtener_datos_panel_facturacion(organizacion_id=organizacion.id, modelos=modelos)
            resultado = deserializar_previsualizacion(request.form.get("documento"))
            huellas = huellas_lotes_tenant(modelos["LoteImportacionFiscal"], organizacion.id)
            validar_confirmacion(
                resultado, organizacion_id=organizacion.id, entidades=datos["entidades_fiscales"],
                puntos=datos["puntos_venta"], tipos=datos["tipos_comprobante"],
                referencias_existentes=[b.referencia_externa for b in datos["borradores"]],
                huellas_existentes=huellas,
            )
            lote = confirmar_importacion(
                resultado, organizacion_id=organizacion.id, usuario=usuario,
                nombre_archivo=request.form.get("nombre_archivo"),
                BorradorComprobanteFiscal=modelos["BorradorComprobanteFiscal"], BorradorItemFiscal=modelos["BorradorItemFiscal"],
                EventoFiscal=modelos["EventoFiscal"], LoteImportacionFiscal=modelos["LoteImportacionFiscal"], db_session=db.session,
            )
            return redirect(url_for("admin_facturacion.panel", ok=f"Lote fiscal #{lote.id} confirmado como borradores. Emisión real bloqueada."))
        except Exception as exc:
            db.session.rollback()
            return redirect(url_for("admin_facturacion.importacion_offline", error=str(exc)))

    @blueprint.route("/admin/facturacion/lotes")
    @login_required
    def lotes_fiscales():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        lotes = listar_lotes(modelos["LoteImportacionFiscal"], organizacion_id=organizacion.id)
        return render_template("admin_lotes_fiscales.html", lotes=lotes, error=(request.args.get("error") or "").strip())

    @blueprint.route("/admin/facturacion/lotes/<int:lote_id>/exportar")
    @login_required
    def exportar_lote_fiscal(lote_id):
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        try:
            lote = obtener_lote(modelos["LoteImportacionFiscal"], organizacion_id=organizacion.id, lote_id=lote_id)
            return send_file(exportar_lote(lote), as_attachment=True, download_name=f"lote_fiscal_{lote.id}.json", mimetype="application/json")
        except Exception as exc:
            return redirect(url_for("admin_facturacion.lotes_fiscales", error=str(exc)))

    @blueprint.route("/admin/facturacion/lotes/<int:lote_id>/anular", methods=["POST"])
    @login_required
    def anular_lote_fiscal(lote_id):
        usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        try:
            lote = obtener_lote(modelos["LoteImportacionFiscal"], organizacion_id=organizacion.id, lote_id=lote_id)
            resultado = anular_lote(lote, motivo=request.form.get("motivo"), usuario=usuario, BorradorComprobanteFiscal=modelos["BorradorComprobanteFiscal"], EventoFiscal=modelos["EventoFiscal"], db_session=db.session)
            return redirect(url_for("admin_facturacion.panel", ok=f"Lote fiscal #{resultado['lote_id']} anulado; {resultado['borradores_cancelados']} borradores cancelados."))
        except Exception as exc:
            db.session.rollback()
            return redirect(url_for("admin_facturacion.lotes_fiscales", error=str(exc)))

    return blueprint
