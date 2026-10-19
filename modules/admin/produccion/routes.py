"""Panel administrativo de planificación productiva bloqueada."""

from flask import Blueprint, redirect, render_template, request, send_file, session, url_for

from services.produccion_consultas import obtener_panel
from services.destino_produccion import guardar_destino, leer_destino, validar_destino
from services.produccion_nucleo import cambiar_estado, crear_orden_preparatoria
from services.avances_produccion import registrar_parte
from services.simulacion_cierre_produccion import exportar_simulacion, simular_cierre
from services.control_integral_produccion import controlar_produccion, exportar_control
from services.propuestas_inventario_produccion import preparar_propuesta_inventario, exportar_propuesta
from services.plan_materiales_produccion import planificar_materiales, exportar_plan
from services.plan_capacidad_produccion import planificar_capacidad, exportar_capacidad
from services.calidad_produccion import crear_lote, registrar_control, evidencia_calidad, exportar_evidencia, elegibilidad_inventario
from services.costeo_resultado_produccion import costear_resultado, exportar_costeo
from services.expediente_habilitacion_produccion import construir_expediente, exportar_expediente
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

    def destinos_guardados(ordenes, organizacion_id, unidad_negocio_id):
        return {orden.id: leer_destino(
            orden=orden, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
            ConfiguracionSistema=modelos["ConfiguracionSistema"],
        ) for orden in ordenes}

    @blueprint.route("/admin/produccion")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        datos = obtener_panel(organizacion.id, unidad.id, modelos=modelos)
        existencias = modelos["ExistenciaSucursal"].query.filter_by(
            organizacion_id=organizacion.id,
        ).all()
        opciones = {}
        for orden in datos["ordenes_produccion"]:
            opciones[orden.id] = []
            for existencia in existencias:
                try:
                    validar_destino(orden, existencia, organizacion.id, unidad.id)
                except ValueError:
                    continue
                opciones[orden.id].append(existencia)
        mapeos = modelos["MapeoInsumoInventario"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).all()
        materiales = planificar_materiales(organizacion_id=organizacion.id,
            unidad_negocio_id=unidad.id, ordenes=datos["ordenes_produccion"], mapeos_insumo=mapeos)
        calidad_ordenes = {orden.id: elegibilidad_inventario(orden,
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id)
            for orden in datos["ordenes_produccion"] if orden.estado == "aprobada"}
        return render_template(
            "admin_produccion.html", organizacion=organizacion, unidad_activa=unidad,
            ok_feedback=request.args.get("ok"), error=request.args.get("error"),
            destinos_por_orden=destinos_guardados(datos["ordenes_produccion"], organizacion.id, unidad.id),
            opciones_destino_por_orden=opciones, materiales_preparacion=materiales,
            calidad_por_orden=calidad_ordenes, **datos,
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
            elif accion == "guardar_destino":
                orden = modelos["OrdenProduccion"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                existencia = modelos["ExistenciaSucursal"].query.filter_by(
                    id=int(request.form.get("destino_existencia_id")), organizacion_id=organizacion.id,
                ).first()
                if orden is None:
                    raise ValueError("La orden no pertenece al contexto activo.")
                guardar_destino(
                    orden=orden, existencia=existencia, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, ConfiguracionSistema=modelos["ConfiguracionSistema"],
                    db_session=db.session,
                )
                mensaje = f"Destino preparatorio de {orden.numero} guardado. Sin movimientos de stock."
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
            elif accion == "registrar_parte":
                orden = modelos["OrdenProduccion"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None: raise ValueError("La orden no pertenece al contexto activo.")
                parte = registrar_parte(
                    request.form, orden=orden, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, ParteProduccion=modelos["ParteProduccion"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Parte {parte.numero} informado sin consumos ni altas de stock."
            elif accion == "crear_lote":
                orden = modelos["OrdenProduccion"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                parte = modelos["ParteProduccion"].query.filter_by(
                    id=int(request.form.get("parte_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None or parte is None: raise ValueError("Orden o parte fuera del contexto activo.")
                lote = crear_lote(
                    request.form, orden=orden, parte=parte, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, LoteProduccion=modelos["LoteProduccion"],
                    db_session=db.session, usuario_id=getattr(usuario,"id",None),
                )
                mensaje = f"Lote {lote.codigo} creado en cuarentena, sin ingreso a stock."
            elif accion == "control_calidad":
                lote = modelos["LoteProduccion"].query.filter_by(
                    id=int(request.form.get("lote_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if lote is None: raise ValueError("El lote no pertenece al contexto activo.")
                control = registrar_control(
                    request.form, lote=lote, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, ControlCalidadProduccion=modelos["ControlCalidadProduccion"],
                    db_session=db.session, usuario_id=getattr(usuario,"id",None),
                )
                mensaje = f"Control {control.numero} registrado; el lote continúa fuera del stock."
            else:
                raise ValueError("La acción productiva no es válida.")
            dependencias["registrar_auditoria"]("Producción preparatoria", entidad="produccion", detalle=mensaje)
            return redirect(url_for("admin_produccion.panel", ok=mensaje, _anchor="destinos-produccion" if accion == "guardar_destino" else None))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_produccion.panel", error=str(error), _anchor="destinos-produccion" if request.form.get("accion") == "guardar_destino" else None))

    @blueprint.route("/admin/produccion/orden/<int:orden_id>/simulacion")
    @dependencias["login_required"]
    def simulacion(orden_id):
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        orden = modelos["OrdenProduccion"].query.filter_by(
            id=orden_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).first()
        if orden is None:
            return redirect(url_for("admin_produccion.panel", error="La orden no pertenece al contexto activo."))
        try:
            resultado = simular_cierre(
                orden, organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
            )
            return send_file(
                exportar_simulacion(resultado), as_attachment=True,
                download_name=f"simulacion_cierre_produccion_{orden.id}.json",
                mimetype="application/json",
            )
        except ValueError as error:
            return redirect(url_for("admin_produccion.panel", error=str(error)))

    @blueprint.route("/admin/produccion/control-integral")
    @dependencias["login_required"]
    def control_integral():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        ordenes = modelos["OrdenProduccion"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).order_by(modelos["OrdenProduccion"].id.asc()).all()
        resultado = controlar_produccion(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id, ordenes=ordenes,
        )
        return send_file(
            exportar_control(resultado), as_attachment=True,
            download_name="control_integral_produccion.json", mimetype="application/json",
        )

    @blueprint.route("/admin/produccion/orden/<int:orden_id>/propuesta-inventario")
    @dependencias["login_required"]
    def propuesta_inventario(orden_id):
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        orden = modelos["OrdenProduccion"].query.filter_by(
            id=orden_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).first()
        if orden is None:
            return redirect(url_for("admin_produccion.panel", error="La orden no pertenece al contexto activo."))
        mapeos = modelos["MapeoInsumoInventario"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).all()
        existencias = modelos["ExistenciaSucursal"].query.filter_by(
            organizacion_id=organizacion.id, producto_id=orden.producto_id,
        ).all()
        try:
            resultado = preparar_propuesta_inventario(
                orden, organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                mapeos_insumo=mapeos, existencias_producto=existencias,
                destino_existencia_id=leer_destino(
                    orden=orden, organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    ConfiguracionSistema=modelos["ConfiguracionSistema"],
                ),
            )
            return send_file(
                exportar_propuesta(resultado), as_attachment=True,
                download_name=f"propuesta_inventario_produccion_{orden.id}.json",
                mimetype="application/json",
            )
        except ValueError as error:
            return redirect(url_for("admin_produccion.panel", error=str(error)))

    @blueprint.route("/admin/produccion/plan-materiales")
    @dependencias["login_required"]
    def plan_materiales():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        ordenes = modelos["OrdenProduccion"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).order_by(modelos["OrdenProduccion"].id.asc()).all()
        mapeos = modelos["MapeoInsumoInventario"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).all()
        resultado = planificar_materiales(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
            ordenes=ordenes, mapeos_insumo=mapeos,
        )
        return send_file(
            exportar_plan(resultado), as_attachment=True,
            download_name="plan_materiales_produccion.json", mimetype="application/json",
        )

    @blueprint.route("/admin/produccion/plan-capacidad")
    @dependencias["login_required"]
    def plan_capacidad():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        ordenes = modelos["OrdenProduccion"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).order_by(modelos["OrdenProduccion"].id.asc()).all()
        versiones_empleado = modelos["EmpleadoCostoVersion"].query.join(
            modelos["EmpleadoProductivo"],
            modelos["EmpleadoCostoVersion"].empleado_id == modelos["EmpleadoProductivo"].id,
        ).filter(
            modelos["EmpleadoProductivo"].organizacion_id == organizacion.id,
            modelos["EmpleadoProductivo"].unidad_negocio_id == unidad.id,
            modelos["EmpleadoCostoVersion"].vigente.is_(True),
        ).all()
        versiones_maquina = modelos["MaquinaCostoVersion"].query.join(
            modelos["MaquinaProductiva"],
            modelos["MaquinaCostoVersion"].maquina_id == modelos["MaquinaProductiva"].id,
        ).filter(
            modelos["MaquinaProductiva"].organizacion_id == organizacion.id,
            modelos["MaquinaProductiva"].unidad_negocio_id == unidad.id,
            modelos["MaquinaCostoVersion"].vigente.is_(True),
        ).all()
        resultado = planificar_capacidad(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id, ordenes=ordenes,
            versiones_empleado=versiones_empleado, versiones_maquina=versiones_maquina,
        )
        return send_file(
            exportar_capacidad(resultado), as_attachment=True,
            download_name="plan_capacidad_produccion.json", mimetype="application/json",
        )

    @blueprint.route("/admin/produccion/evidencia-calidad")
    @dependencias["login_required"]
    def descargar_evidencia_calidad():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        lotes = modelos["LoteProduccion"].query.filter_by(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).order_by(modelos["LoteProduccion"].id.asc()).all()
        resultado=evidencia_calidad(organizacion_id=organizacion.id,unidad_negocio_id=unidad.id,lotes=lotes)
        return send_file(exportar_evidencia(resultado),as_attachment=True,
                         download_name="evidencia_calidad_produccion.json",mimetype="application/json")

    @blueprint.route("/admin/produccion/orden/<int:orden_id>/costeo-resultado")
    @dependencias["login_required"]
    def costeo_resultado(orden_id):
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        orden = modelos["OrdenProduccion"].query.filter_by(
            id=orden_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
        ).first()
        if orden is None:
            return redirect(url_for("admin_produccion.panel", error="La orden no pertenece al contexto activo."))
        try:
            resultado=costear_resultado(orden,organizacion_id=organizacion.id,unidad_negocio_id=unidad.id)
            return send_file(exportar_costeo(resultado),as_attachment=True,
                             download_name=f"costeo_resultado_produccion_{orden.id}.json",
                             mimetype="application/json")
        except ValueError as error:
            return redirect(url_for("admin_produccion.panel",error=str(error)))

    @blueprint.route("/admin/produccion/expediente-habilitacion")
    @dependencias["login_required"]
    def expediente_habilitacion():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None: return respuesta
        ordenes=modelos["OrdenProduccion"].query.filter_by(
            organizacion_id=organizacion.id,unidad_negocio_id=unidad.id,
        ).order_by(modelos["OrdenProduccion"].id.asc()).all()
        mapeos=modelos["MapeoInsumoInventario"].query.filter_by(
            organizacion_id=organizacion.id,unidad_negocio_id=unidad.id,
        ).all()
        productos={item.producto_id for item in ordenes}
        existencias=modelos["ExistenciaSucursal"].query.filter(
            modelos["ExistenciaSucursal"].organizacion_id==organizacion.id,
            modelos["ExistenciaSucursal"].producto_id.in_(productos),
        ).all() if productos else []
        empleados=modelos["EmpleadoCostoVersion"].query.join(modelos["EmpleadoProductivo"]).filter(
            modelos["EmpleadoProductivo"].organizacion_id==organizacion.id,
            modelos["EmpleadoProductivo"].unidad_negocio_id==unidad.id,
            modelos["EmpleadoCostoVersion"].vigente.is_(True),
        ).all()
        maquinas=modelos["MaquinaCostoVersion"].query.join(modelos["MaquinaProductiva"]).filter(
            modelos["MaquinaProductiva"].organizacion_id==organizacion.id,
            modelos["MaquinaProductiva"].unidad_negocio_id==unidad.id,
            modelos["MaquinaCostoVersion"].vigente.is_(True),
        ).all()
        lotes=modelos["LoteProduccion"].query.filter_by(
            organizacion_id=organizacion.id,unidad_negocio_id=unidad.id,
        ).order_by(modelos["LoteProduccion"].id.asc()).all()
        resultado=construir_expediente(
            organizacion_id=organizacion.id,unidad_negocio_id=unidad.id,ordenes=ordenes,
            mapeos_insumo=mapeos,existencias_producto=existencias,
            versiones_empleado=empleados,versiones_maquina=maquinas,lotes=lotes,
            destinos_por_orden=destinos_guardados(ordenes, organizacion.id, unidad.id),
        )
        return send_file(exportar_expediente(resultado),as_attachment=True,
                         download_name="expediente_habilitacion_produccion.json",mimetype="application/json")

    return blueprint
