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
from services.modulos_organizacion import asegurar_modulos_iniciales
from services.onboarding_saas import (
    actualizar_organizacion,
    actualizar_unidad,
    cambiar_estado_organizacion,
    cambiar_estado_unidad,
    crear_organizacion,
    crear_unidad,
)
from services.asignacion_tenant_pedidos import (
    aplicar_lote_tenant,
    aplicar_propuesta_tenant,
    aprobar_lote_tenant,
    aprobar_propuesta_tenant,
    preparar_propuestas_tenant,
    previsualizar_lote_tenant,
    rechazar_propuesta_tenant,
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

    def membresias_usuario(usuario):
        return (
            UsuarioOrganizacion.query
            .filter_by(usuario_id=usuario.id, activa=True)
            .order_by(UsuarioOrganizacion.id.asc())
            .all()
        )

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
        usuario, organizacion, respuesta = (
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
            membresias_tenant=membresias_usuario(usuario),
            puede_crear_tenant=(usuario.rol == "admin"),
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
            if accion == "seleccionar_organizacion":
                membresia = resolver_tenant_usuario(
                    usuario,
                    UsuarioOrganizacion=UsuarioOrganizacion,
                    organizacion_id=request.form.get("organizacion_id"),
                )
                session["organizacion_id"] = membresia.organizacion_id
                return redirect(url_for("admin_estructura.panel"))
            if accion == "crear_organizacion":
                if usuario.rol != "admin":
                    raise ValueError("No tenés permiso para crear organizaciones.")
                nueva = crear_organizacion(
                    nombre=request.form.get("nombre"),
                    slug=request.form.get("slug"),
                    unidad_nombre=request.form.get("unidad_nombre"),
                    unidad_codigo=request.form.get("unidad_codigo"),
                    usuario=usuario,
                    Organizacion=modelos["Organizacion"],
                    UnidadNegocio=modelos["UnidadNegocio"],
                    UsuarioOrganizacion=UsuarioOrganizacion,
                    ModuloOrganizacion=modelos["ModuloOrganizacion"],
                    db_session=db.session,
                    asegurar_modulos_fn=asegurar_modulos_iniciales,
                )
                mensaje = f"Organización {nueva.nombre} creada desactivada."
            elif accion == "estado_organizacion":
                if usuario.rol != "admin":
                    raise ValueError("No tenés permiso para cambiar organizaciones.")
                objetivo = cambiar_estado_organizacion(
                    request.form.get("organizacion_id"),
                    usuario_id=usuario.id,
                    Organizacion=modelos["Organizacion"],
                    UsuarioOrganizacion=UsuarioOrganizacion,
                    db_session=db.session,
                )
                mensaje = f"Organización {objetivo.nombre} actualizada."
            elif accion == "editar_organizacion":
                actualizar_organizacion(
                    organizacion,
                    nombre=request.form.get("nombre"),
                    slug=request.form.get("slug"),
                    Organizacion=modelos["Organizacion"],
                    db_session=db.session,
                )
                mensaje = "Datos de la organización actualizados."
            elif accion == "crear_unidad":
                unidad = crear_unidad(
                    organizacion,
                    nombre=request.form.get("nombre"),
                    codigo=request.form.get("codigo"),
                    UnidadNegocio=modelos["UnidadNegocio"],
                    db_session=db.session,
                )
                mensaje = f"Unidad {unidad.nombre} creada desactivada."
            elif accion == "editar_unidad":
                actualizar_unidad(
                    organizacion,
                    request.form.get("unidad_id"),
                    nombre=request.form.get("nombre"),
                    codigo=request.form.get("codigo"),
                    UnidadNegocio=modelos["UnidadNegocio"],
                    db_session=db.session,
                )
                mensaje = "Unidad actualizada."
            elif accion == "toggle_unidad":
                unidad = cambiar_estado_unidad(
                    organizacion,
                    request.form.get("unidad_id"),
                    UnidadNegocio=modelos["UnidadNegocio"],
                    db_session=db.session,
                )
                mensaje = f"Unidad {unidad.nombre} actualizada."
            elif accion == "preparar_asignaciones_pedidos":
                cantidad = preparar_propuestas_tenant(
                    organizacion.id,
                    Pedido=modelos["Pedido"],
                    VinculoCanalComercial=modelos["VinculoCanalComercial"],
                    AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
                    db_session=db.session,
                    usuario=usuario,
                )
                mensaje = f"Propuestas preparadas: {cantidad}. Ningún pedido fue modificado."
            elif accion == "aprobar_asignacion_pedido":
                aprobar_propuesta_tenant(
                    request.form.get("propuesta_id"),
                    organizacion.id,
                    Pedido=modelos["Pedido"],
                    VinculoCanalComercial=modelos["VinculoCanalComercial"],
                    AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
                    db_session=db.session,
                    usuario=usuario,
                )
                mensaje = "Propuesta aprobada; el pedido todavía no fue modificado."
            elif accion == "rechazar_asignacion_pedido":
                rechazar_propuesta_tenant(
                    request.form.get("propuesta_id"),
                    organizacion.id,
                    motivo=request.form.get("motivo"),
                    AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
                    db_session=db.session,
                    usuario=usuario,
                )
                mensaje = "Propuesta rechazada."
            elif accion == "aplicar_asignacion_pedido":
                aplicar_propuesta_tenant(
                    request.form.get("propuesta_id"),
                    organizacion.id,
                    confirmacion=request.form.get("confirmacion"),
                    Pedido=modelos["Pedido"],
                    VinculoCanalComercial=modelos["VinculoCanalComercial"],
                    AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
                    db_session=db.session,
                    usuario=usuario,
                )
                mensaje = "Identidad tenant aplicada al pedido. No se ejecutaron acciones externas."
            elif accion == "aprobar_lote_asignaciones":
                cantidad = aprobar_lote_tenant(
                    request.form.getlist("propuesta_id"), organizacion.id,
                    Pedido=modelos["Pedido"],
                    VinculoCanalComercial=modelos["VinculoCanalComercial"],
                    AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
                    db_session=db.session, usuario=usuario,
                )
                mensaje = f"Lote aprobado: {cantidad} propuestas. Ningún pedido fue modificado."
            elif accion == "aplicar_lote_asignaciones":
                cantidad = aplicar_lote_tenant(
                    request.form.getlist("propuesta_id"), organizacion.id,
                    confirmacion=request.form.get("confirmacion"),
                    Pedido=modelos["Pedido"],
                    VinculoCanalComercial=modelos["VinculoCanalComercial"],
                    AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
                    db_session=db.session, usuario=usuario,
                )
                mensaje = f"Lote aplicado: {cantidad} pedidos. Sin acciones externas."
            else:
                mensaje = procesar_accion_estructura_admin(
                    accion, request.form, organizacion=organizacion,
                    modelos=modelos, db_session=db.session,
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

    @blueprint.route(
        "/admin/estructura/asignaciones/previsualizar",
        methods=["POST"],
    )
    @login_required
    def previsualizar_asignaciones():
        _usuario_actual, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        operacion = (request.form.get("operacion") or "aprobar").strip().lower()
        if operacion not in {"aprobar", "aplicar"}:
            return redirect(url_for(
                "admin_estructura.panel", error="La operación masiva no es válida."
            ))
        try:
            vista = previsualizar_lote_tenant(
                request.form.getlist("propuesta_id"), organizacion.id,
                estado_requerido=("preparada" if operacion == "aprobar" else "aprobada"),
                Pedido=modelos["Pedido"],
                VinculoCanalComercial=modelos["VinculoCanalComercial"],
                AsignacionTenantPedido=modelos["AsignacionTenantPedido"],
            )
            return render_template(
                "admin_previsualizacion_asignaciones_pedidos.html",
                organizacion=organizacion, operacion=operacion, vista=vista,
            )
        except Exception as error:
            return redirect(url_for(
                "admin_estructura.panel", error=str(error),
            ))

    return blueprint
