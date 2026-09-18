"""Panel administrativo de planificación productiva bloqueada."""

from flask import Blueprint, redirect, render_template, request, session, url_for

from services.produccion_consultas import obtener_panel
from services.produccion_nucleo import cambiar_estado, crear_orden_preparatoria
from services.tenant_context import TenantError, resolver_tenant_usuario


def crear_blueprint_produccion(*, dependencias):
    blueprint = Blueprint("admin_produccion", __name__)
    db = dependencias["db"]
    modelos = dependencias["modelos"]

    def acceso():
        usuario = dependencias["usuario_actual"]()
        try:
            membresia = resolver_tenant_usuario(
                usuario, UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],
                organizacion_id=session.get("organizacion_id"),
            )
        except TenantError as error:
            return None, None, None, redirect(url_for("inicio", error=str(error)))
        if membresia.rol != "admin":
            return None, None, None, redirect(url_for("inicio"))
        unidad = modelos["UnidadNegocio"].query.filter_by(
            id=session.get("unidad_negocio_id"), organizacion_id=membresia.organizacion_id, activa=True,
        ).first()
        if unidad is None:
            unidad = modelos["UnidadNegocio"].query.filter_by(
                organizacion_id=membresia.organizacion_id, activa=True,
            ).order_by(modelos["UnidadNegocio"].id.asc()).first()
        if unidad is None:
            return usuario, membresia.organizacion, None, redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"] = membresia.organizacion_id
        session["unidad_negocio_id"] = unidad.id
        return usuario, membresia.organizacion, unidad, None

    @blueprint.route("/admin/produccion")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        return render_template(
            "admin_produccion.html", organizacion=organizacion, unidad_activa=unidad,
            ok_feedback=request.args.get("ok"), error=request.args.get("error"),
            **obtener_panel(organizacion.id, unidad.id, modelos=modelos),
        )

    @blueprint.route("/admin/produccion/guardar", methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        try:
            accion = request.form.get("accion")
            if accion == "crear_orden":
                perfil = modelos["PerfilCosteoProducto"].query.filter_by(
                    id=int(request.form.get("perfil_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, tipo="produccion", activo=True,
                ).first()
                if perfil is None: raise ValueError("El perfil no pertenece al tenant y unidad activos.")
                version = modelos["CostoProductoVersion"].query.filter_by(
                    organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    producto_id=perfil.producto_id, vigente=True,
                ).first()
                orden = crear_orden_preparatoria(
                    request.form, perfil=perfil, version_costo=version,
                    organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    modelos=modelos, db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Orden {orden.numero} preparada sin ejecución."
            elif accion == "cambiar_estado":
                orden = modelos["OrdenProduccion"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None: raise ValueError("La orden no pertenece al contexto activo.")
                cambiar_estado(
                    orden, request.form.get("estado"), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, db_session=db.session,
                )
                mensaje = f"Orden {orden.numero} actualizada a {orden.estado}; ejecución bloqueada."
            else:
                raise ValueError("La acción productiva no es válida.")
            dependencias["registrar_auditoria"]("Producción preparatoria", entidad="produccion", detalle=mensaje)
            return redirect(url_for("admin_produccion.panel", ok=mensaje))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_produccion.panel", error=str(error)))

    return blueprint
