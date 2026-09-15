"""
Blueprint administrativo del CRM interno.

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

from services.crm_admin import (
    procesar_accion_crm_admin,
)
from services.crm_consultas import (
    obtener_datos_panel_crm,
)
from services.certificacion_offline_crm import certificar_crm,exportar_certificacion
from services.importacion_offline_crm import exportar_previsualizacion,previsualizar_importacion
from services.confirmacion_importacion_crm import deserializar_plan,validar_confirmacion,confirmar_importacion
from services.gestion_lotes_crm import anular_lote,exportar_evidencia,obtener_lote_tenant
from services.control_integral_crm import controlar_crm,exportar_control
from services.tenant_context import (
    TenantError,
    resolver_tenant_usuario,
)


def crear_blueprint_crm(
    *,
    dependencias,
):
    blueprint = Blueprint(
        "admin_crm",
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

    @blueprint.route("/admin/crm")
    @login_required
    def panel():
        _usuario, organizacion, respuesta = (
            resolver_acceso()
        )

        if respuesta is not None:
            return respuesta

        datos = obtener_datos_panel_crm(
            organizacion.id,
            modelos=modelos,
        )

        return render_template(
            "admin_crm.html",
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
        "/admin/crm/guardar",
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
            mensaje = procesar_accion_crm_admin(
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

            registrar_auditoria(
                "Configuró CRM interno",
                entidad="crm",
                entidad_id=organizacion.id,
                detalle=(
                    f"Acción: {accion}. {mensaje}"
                ),
            )

            return redirect(url_for(
                "admin_crm.panel",
                ok=mensaje,
            ))

        except Exception as error:
            db.session.rollback()

            print(
                "[CRM ADMIN] "
                f"No se pudo ejecutar {accion}: "
                f"{error}"
            )

            return redirect(url_for(
                "admin_crm.panel",
                error=str(error),
            ))

    @blueprint.route("/admin/crm/certificacion-offline",methods=["GET","POST"])
    @login_required
    def certificacion_offline():
        _usuario,organizacion,respuesta=resolver_acceso()
        if respuesta is not None:return respuesta
        datos=obtener_datos_panel_crm(organizacion.id,modelos=modelos)
        resultado=certificar_crm(organizacion_id=organizacion.id,modulo=datos["modulo_crm"],unidades=datos["unidades"],etapas=datos["etapas"],clientes=datos["clientes"],identidades=datos["identidades"],oportunidades=datos["oportunidades"],actividades=datos["actividades"])
        if request.method=="POST":return send_file(exportar_certificacion(resultado),as_attachment=True,download_name="certificacion_crm_offline.json",mimetype="application/json")
        return render_template("admin_certificacion_crm_offline.html",certificacion=resultado)

    @blueprint.route("/admin/crm/importacion-offline", methods=["GET", "POST"])
    @login_required
    def importacion_offline():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_datos_panel_crm(organizacion.id, modelos=modelos)
        resultado = None
        error = ""
        if request.method == "POST":
            try:
                archivo = request.files.get("archivo")
                if archivo is None or not archivo.filename:
                    raise ValueError("Seleccioná un archivo CSV.")
                resultado = previsualizar_importacion(
                    archivo.read(),
                    organizacion_id=organizacion.id,
                    unidades=datos["unidades"],
                    etapas=datos["etapas"],
                    clientes=datos["clientes"],
                    identidades=datos["identidades"],
                )
                if request.form.get("accion") == "exportar":
                    return send_file(
                        exportar_previsualizacion(resultado),
                        as_attachment=True,
                        download_name="previsualizacion_crm_offline.json",
                        mimetype="application/json",
                    )
            except ValueError as excepcion:
                error = str(excepcion)
        return render_template(
            "admin_importacion_crm_offline.html",
            resultado=resultado,
            error=error,
            organizacion=organizacion,
            lotes=datos["lotes_importacion"],
        )

    @blueprint.route("/admin/crm/importacion-offline/confirmar", methods=["POST"])
    @login_required
    def confirmar_importacion_offline():
        usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        archivo = request.files.get("plan")
        try:
            if archivo is None or not archivo.filename:
                raise ValueError("Seleccioná la previsualización JSON exportada.")
            datos = obtener_datos_panel_crm(organizacion.id, modelos=modelos)
            plan = deserializar_plan(archivo.read())
            validar_confirmacion(
                plan,
                organizacion_id=organizacion.id,
                unidades=datos["unidades"],
                etapas=datos["etapas"],
                clientes=datos["clientes"],
                identidades=datos["identidades"],
                lotes=datos["lotes_importacion"],
            )
            lote = confirmar_importacion(
                plan,
                organizacion_id=organizacion.id,
                usuario=usuario,
                nombre_archivo=archivo.filename,
                clientes_existentes=datos["clientes"],
                modelos=modelos,
                db_session=db.session,
            )
            registrar_auditoria(
                "Confirmó lote CRM offline",
                entidad="lote_importacion_crm",
                entidad_id=lote.id,
                detalle=f"Clientes: {lote.clientes_creados}; oportunidades: {lote.oportunidades_creadas}; actividades: {lote.actividades_creadas}.",
            )
            return redirect(url_for("admin_crm.importacion_offline", ok=f"Lote CRM #{lote.id} confirmado."))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_crm.importacion_offline", error=str(error)))

    @blueprint.route("/admin/crm/lotes/<int:lote_id>/evidencia")
    @login_required
    def evidencia_lote(lote_id):
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        lote = obtener_lote_tenant(lote_id, organizacion_id=organizacion.id, LoteImportacionCRM=modelos["LoteImportacionCRM"])
        return send_file(exportar_evidencia(lote), as_attachment=True, download_name=f"lote_crm_{lote.id}.json", mimetype="application/json")

    @blueprint.route("/admin/crm/lotes/<int:lote_id>/anular", methods=["POST"])
    @login_required
    def anular_lote_importacion(lote_id):
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        try:
            lote = obtener_lote_tenant(lote_id, organizacion_id=organizacion.id, LoteImportacionCRM=modelos["LoteImportacionCRM"])
            anular_lote(lote, organizacion_id=organizacion.id, db_session=db.session)
            registrar_auditoria("Anuló lote CRM", entidad="lote_importacion_crm", entidad_id=lote.id, detalle="Anulación interna; los registros y la evidencia se conservaron.")
            return redirect(url_for("admin_crm.importacion_offline", ok=f"Lote CRM #{lote.id} anulado."))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_crm.importacion_offline", error=str(error)))

    @blueprint.route("/admin/crm/control-integral", methods=["GET", "POST"])
    @login_required
    def control_integral():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_datos_panel_crm(organizacion.id, modelos=modelos)
        resultado = controlar_crm(
            organizacion_id=organizacion.id,
            modulo=datos["modulo_crm"], unidades=datos["unidades"], etapas=datos["etapas"],
            clientes=datos["clientes"], identidades=datos["identidades"], oportunidades=datos["oportunidades"],
            actividades=datos["actividades"], lotes=datos["lotes_importacion"],
        )
        if request.method == "POST":
            return send_file(exportar_control(resultado), as_attachment=True, download_name="control_integral_crm.json", mimetype="application/json")
        return render_template("admin_control_integral_crm.html", control=resultado)

    return blueprint
