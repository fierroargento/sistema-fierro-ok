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
    send_file,
    session,
    url_for,
)
from services.control_integral_estructura_saas import controlar_estructura,exportar_control
from services.certificacion_consolidada_saas import consolidar_certificaciones,exportar_expediente
from services.plan_corte_dux import construir_plan,exportar_plan
from services.ensayo_corte_dux import ensayar_corte,exportar_ensayo
from services.snapshots_corte_dux import construir_snapshot_fierro,plantilla_snapshot_dux,exportar as exportar_snapshot
from services.importacion_snapshot_dux import convertir_exportaciones,exportar as exportar_snapshot_dux,plantilla_productos,plantilla_pedidos
from services.expediente_transicion_dux import construir_expediente as construir_expediente_transicion,exportar as exportar_expediente_transicion
from services.expediente_maestro_preparacion import construir_expediente as construir_expediente_maestro,exportar as exportar_expediente_maestro

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

    @blueprint.route("/admin/estructura/control-integral", methods=["GET", "POST"])
    @login_required
    def control_integral():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_datos_panel_estructura(organizacion.id, modelos=modelos)
        resultado = controlar_estructura(organizacion=organizacion, datos=datos)
        if request.method == "POST":
            return send_file(exportar_control(resultado), as_attachment=True, download_name="control_integral_estructura_saas.json", mimetype="application/json")
        return render_template("admin_control_estructura_saas.html", control=resultado, organizacion=organizacion)

    @blueprint.route("/admin/estructura/certificacion-consolidada", methods=["GET", "POST"])
    @login_required
    def certificacion_consolidada():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        resultado = None
        error = ""
        if request.method == "POST":
            try:
                resultado = consolidar_certificaciones(request.files.getlist("certificaciones"), organizacion_id=organizacion.id)
                if request.form.get("accion") == "exportar":
                    return send_file(exportar_expediente(resultado), as_attachment=True, download_name="expediente_consolidado_saas.json", mimetype="application/json")
            except ValueError as excepcion:
                error = str(excepcion)
        return render_template("admin_certificacion_consolidada_saas.html", resultado=resultado, error=error, organizacion=organizacion)

    @blueprint.route("/admin/estructura/plan-corte-dux", methods=["GET", "POST"])
    @login_required
    def plan_corte_dux():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        resultado = construir_plan(request.form, organizacion_id=organizacion.id) if request.method == "POST" else None
        if resultado is not None and request.form.get("accion") == "exportar":
            return send_file(exportar_plan(resultado), as_attachment=True, download_name="plan_corte_dux_no_ejecutable.json", mimetype="application/json")
        return render_template("admin_plan_corte_dux.html", resultado=resultado, organizacion=organizacion)

    @blueprint.route("/admin/estructura/ensayo-corte-dux", methods=["GET", "POST"])
    @login_required
    def ensayo_corte_dux():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        resultado = None; error = ""
        if request.method == "POST":
            try:
                resultado = ensayar_corte(request.files.get("snapshot_dux"), request.files.get("snapshot_fierro"), organizacion_id=organizacion.id)
                if request.form.get("accion") == "exportar":return send_file(exportar_ensayo(resultado),as_attachment=True,download_name="ensayo_corte_dux_offline.json",mimetype="application/json")
            except (ValueError,TypeError) as excepcion:error=str(excepcion)
        return render_template("admin_ensayo_corte_dux.html",resultado=resultado,error=error,organizacion=organizacion)

    @blueprint.route("/admin/estructura/snapshot-corte/<origen>")
    @login_required
    def snapshot_corte(origen):
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:return respuesta
        if origen == "dux":return send_file(exportar_snapshot(plantilla_snapshot_dux()),as_attachment=True,download_name="plantilla_snapshot_dux.json",mimetype="application/json")
        if origen != "fierro":return redirect(url_for("admin_estructura.ensayo_corte_dux",error="Origen de snapshot invalido."))
        unidad_id=session.get("unidad_negocio_id")
        unidad=modelos["UnidadNegocio"].query.filter_by(id=unidad_id,organizacion_id=organizacion.id,activa=True).first() if unidad_id else None
        if unidad is None:unidad=modelos["UnidadNegocio"].query.filter_by(organizacion_id=organizacion.id,activa=True).order_by(modelos["UnidadNegocio"].id.asc()).first()
        if unidad is None:return redirect(url_for("admin_estructura.ensayo_corte_dux",error="No hay una unidad activa para generar el snapshot."))
        unidad_id=unidad.id
        productos=modelos["Producto"].query.filter_by(organizacion_id=organizacion.id).all()
        ids=[p.id for p in productos]
        inclusiones=modelos["CatalogoProducto"].query.filter(modelos["CatalogoProducto"].producto_id.in_(ids)).all() if ids else []
        existencias=modelos["ExistenciaSucursal"].query.filter_by(organizacion_id=organizacion.id).all()
        pedidos=modelos["Pedido"].query.filter_by(organizacion_id=organizacion.id,unidad_negocio_id=unidad_id).all()
        resultado=construir_snapshot_fierro(organizacion_id=organizacion.id,unidad_negocio_id=unidad_id,productos=productos,inclusiones=inclusiones,existencias=existencias,pedidos=pedidos)
        return send_file(exportar_snapshot(resultado),as_attachment=True,download_name="snapshot_sistema_fierro.json",mimetype="application/json")

    @blueprint.route("/admin/estructura/convertir-snapshot-dux", methods=["GET", "POST"])
    @login_required
    def convertir_snapshot_dux():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:return respuesta
        if request.args.get("plantilla") == "productos":return send_file(plantilla_productos(),as_attachment=True,download_name="plantilla_productos_dux.csv",mimetype="text/csv")
        if request.args.get("plantilla") == "pedidos":return send_file(plantilla_pedidos(),as_attachment=True,download_name="plantilla_pedidos_dux.csv",mimetype="text/csv")
        resultado=None;error=""
        if request.method == "POST":
            try:
                resultado=convertir_exportaciones(request.files.get("productos_csv"),request.files.get("pedidos_csv"))
                if request.form.get("accion") == "exportar":return send_file(exportar_snapshot_dux(resultado),as_attachment=True,download_name="snapshot_dux_convertido.json",mimetype="application/json")
            except (ValueError,TypeError) as excepcion:error=str(excepcion)
        return render_template("admin_convertir_snapshot_dux.html",resultado=resultado,error=error,organizacion=organizacion)

    @blueprint.route("/admin/estructura/expediente-transicion-dux", methods=["GET", "POST"])
    @login_required
    def expediente_transicion_dux():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:return respuesta
        resultado=None;error=""
        if request.method == "POST":
            try:
                resultado=construir_expediente_transicion(request.files.get("plan"),request.files.get("ensayo"),request.files.get("certificacion"),organizacion_id=organizacion.id)
                if request.form.get("accion") == "exportar":return send_file(exportar_expediente_transicion(resultado),as_attachment=True,download_name="expediente_transicion_dux.json",mimetype="application/json")
            except (ValueError,TypeError) as excepcion:error=str(excepcion)
        return render_template("admin_expediente_transicion_dux.html",resultado=resultado,error=error,organizacion=organizacion)

    @blueprint.route("/admin/estructura/expediente-maestro", methods=["GET", "POST"])
    @login_required
    def expediente_maestro():
        _usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:return respuesta
        unidad_id=session.get("unidad_negocio_id")
        unidad=modelos["UnidadNegocio"].query.filter_by(id=unidad_id,organizacion_id=organizacion.id,activa=True).first() if unidad_id else None
        if unidad is None:unidad=modelos["UnidadNegocio"].query.filter_by(organizacion_id=organizacion.id,activa=True).order_by(modelos["UnidadNegocio"].id.asc()).first()
        if unidad is None:return redirect(url_for("admin_estructura.panel",error="No hay una unidad activa para construir el expediente maestro."))
        resultado=None;error=""
        if request.method == "POST":
            try:
                resultado=construir_expediente_maestro(request.files.getlist("evidencias"),organizacion_id=organizacion.id,unidad_negocio_id=unidad.id)
                if request.form.get("accion") == "exportar":return send_file(exportar_expediente_maestro(resultado),as_attachment=True,download_name="expediente_maestro_preparacion.json",mimetype="application/json")
            except (ValueError,TypeError) as excepcion:error=str(excepcion)
        return render_template("admin_expediente_maestro_preparacion.html",resultado=resultado,error=error,organizacion=organizacion,unidad=unidad)

    return blueprint
