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

    return blueprint
