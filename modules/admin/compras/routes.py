"""Panel tenant de compras preparatorias sin impacto automático."""

from flask import Blueprint, redirect, render_template, request, send_file, session, url_for

from services.compras_consultas import obtener_panel_compras
from services.compras_nucleo import (
    agregar_item_orden,
    cambiar_estado_orden,
    crear_orden,
    crear_proveedor,
    preparar_recepcion,
    quitar_item_orden,
)
from services.propuestas_impacto_compra import decidir_propuesta, preparar_propuestas
from services.mapeos_compras_inventario import crear_mapeo, habilitar_propuestas_stock
from services.conciliacion_facturas_compra import registrar_factura_preparatoria
from services.control_integral_compras import controlar_compras, exportar_control
from services.importacion_productos_costeo import (
    deserializar, exigir_confirmacion_importacion, leer_archivo, serializar,
)
from services.importacion_proveedores_compra import (
    CAMPOS_PROVEEDORES, aplicar_proveedores, previsualizar_proveedores,
    resumir_proveedores, sugerir_mapeo_proveedores,
)
from services.fechas import ahora_utc_naive
from services.tenant_context import TenantError, resolver_tenant_usuario


def crear_blueprint_compras(*, dependencias):
    blueprint = Blueprint("admin_compras", __name__)
    db = dependencias["db"]
    modelos = dependencias["modelos"]

    def acceso():
        usuario = dependencias["usuario_actual"]()
        try:
            membresia = resolver_tenant_usuario(
                usuario,
                UsuarioOrganizacion=dependencias["UsuarioOrganizacion"],
                organizacion_id=session.get("organizacion_id"),
            )
        except TenantError as error:
            return None, None, None, redirect(url_for("inicio", error=str(error)))
        if membresia.rol != "admin":
            return None, None, None, redirect(url_for("inicio"))
        unidades = modelos["UnidadNegocio"].query.filter_by(
            organizacion_id=membresia.organizacion_id, activa=True,
        ).order_by(modelos["UnidadNegocio"].nombre.asc()).all()
        unidad_id = session.get("unidad_negocio_id")
        unidad = next((item for item in unidades if item.id == unidad_id), None)
        if unidad is None and unidades:
            unidad = unidades[0]
            session["unidad_negocio_id"] = unidad.id
        if unidad is None:
            return usuario, membresia.organizacion, None, redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"] = membresia.organizacion_id
        return usuario, membresia.organizacion, unidad, None

    @blueprint.route("/admin/compras")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_panel_compras(organizacion.id, unidad.id, modelos=modelos)
        return render_template(
            "admin_compras.html", organizacion=organizacion, unidad_activa=unidad,
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(), **datos,
        )

    @blueprint.route("/admin/compras/importar-proveedores", methods=["GET", "POST"])
    @dependencias["login_required"]
    def importar_proveedores():
        usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        Lote = modelos["ImportacionMasivaCosto"]
        tipo_lote = "proveedores_compra"
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename:
                        raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo, request.form.get("hoja"))
                    lote = Lote(
                        organizacion_id=organizacion.id, unidad_negocio_id=None,
                        usuario_id=getattr(usuario, "id", None),
                        tipo_datos=tipo_lote, nombre_archivo=archivo.filename,
                        nombre_hoja=lectura["hoja"], estado="cargado",
                        modo="crear_actualizar",
                        encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(
                            sugerir_mapeo_proveedores(lectura["encabezados"])
                        ), total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote)
                    db.session.commit()
                    return redirect(url_for(
                        "admin_compras.importar_proveedores", lote=lote.id,
                    ))
                lote = Lote.query.filter_by(
                    id=int(request.form.get("lote_id")),
                    organizacion_id=organizacion.id,
                    unidad_negocio_id=None, tipo_datos=tipo_lote,
                ).first()
                if lote is None:
                    raise ValueError("El lote no pertenece a la organización activa.")
                proveedores = modelos["ProveedorCompra"].query.filter_by(
                    organizacion_id=organizacion.id,
                ).all()
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {
                        str(i): (
                            (request.form.get(f"col_{i}") or "").strip()
                            if request.form.get(f"usar_{i}") == "1" else ""
                        ) for i in range(len(encabezados))
                    }
                    vista = previsualizar_proveedores(
                        deserializar(lote.filas_json, []), mapeo,
                        proveedores=proveedores,
                    )
                    lote.mapeo_json = serializar(mapeo)
                    lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"
                    db.session.commit()
                elif accion == "confirmar":
                    exigir_confirmacion_importacion(
                        request.form.get("confirmacion"), "IMPORTAR PROVEEDORES",
                    )
                    if lote.estado != "mapeado":
                        raise ValueError("Primero validá el mapeo.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = previsualizar_proveedores(
                        deserializar(lote.filas_json, []),
                        deserializar(lote.mapeo_json, {}),
                        proveedores=proveedores,
                    )
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual)
                        db.session.commit()
                        return redirect(url_for(
                            "admin_compras.importar_proveedores", lote=lote.id,
                            error=("Los proveedores cambiaron desde la validación. "
                                   "Revisá la vista y confirmá nuevamente."),
                        ))
                    conteos = aplicar_proveedores(
                        vista_actual, organizacion_id=organizacion.id,
                        ProveedorCompra=modelos["ProveedorCompra"],
                        db_session=db.session, commit=False,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items():
                        setattr(lote, campo, valor)
                    lote.estado = "confirmado"
                    lote.fecha_confirmacion = ahora_utc_naive()
                    db.session.commit()
                    dependencias["registrar_auditoria"](
                        "Confirmó importación de proveedores",
                        entidad="importacion_masiva_costo", entidad_id=lote.id,
                        detalle=(f"Organización {organizacion.id}; "
                                 f"{conteos['creados']} creados; "
                                 f"{conteos['actualizados']} actualizados; "
                                 f"{conteos['rechazados']} rechazados."),
                    )
                return redirect(url_for(
                    "admin_compras.importar_proveedores", lote=lote.id,
                ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_compras.importar_proveedores", error=str(error),
            ))
        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(
            id=lote_id, organizacion_id=organizacion.id,
            unidad_negocio_id=None, tipo_datos=tipo_lote,
        ).first() if lote_id else None
        vista = deserializar(lote.vista_previa_json, []) if lote else []
        return render_template(
            "admin_importacion_proveedores.html", organizacion=organizacion,
            unidad_activa=unidad, lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=vista, resumen=resumir_proveedores(vista),
            campos=CAMPOS_PROVEEDORES,
            historial=Lote.query.filter_by(
                organizacion_id=organizacion.id, unidad_negocio_id=None,
                tipo_datos=tipo_lote,
            ).order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/compras/guardar", methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        accion = (request.form.get("accion") or "").strip()
        try:
            if accion == "crear_proveedor":
                creado = crear_proveedor(
                    request.form, organizacion_id=organizacion.id,
                    ProveedorCompra=modelos["ProveedorCompra"], db_session=db.session,
                )
                mensaje = f"Proveedor {creado.codigo} creado."
            elif accion == "crear_orden":
                proveedor = modelos["ProveedorCompra"].query.filter_by(
                    id=int(request.form.get("proveedor_id")), organizacion_id=organizacion.id,
                ).first()
                if proveedor is None:
                    raise ValueError("El proveedor no pertenece al tenant activo.")
                insumo_id = request.form.get("insumo_id")
                insumo = None
                if insumo_id:
                    insumo = modelos["InsumoProductivo"].query.filter_by(
                        id=int(insumo_id), organizacion_id=organizacion.id,
                    ).first()
                    if insumo is None:
                        raise ValueError("El insumo no pertenece al tenant activo.")
                creada = crear_orden(
                    request.form, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id, proveedor=proveedor, insumo=insumo,
                    OrdenCompra=modelos["OrdenCompra"],
                    OrdenCompraItem=modelos["OrdenCompraItem"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Orden {creada.numero} creada como borrador."
            elif accion in {"agregar_item", "quitar_item"}:
                orden = modelos["OrdenCompra"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None:
                    raise ValueError("La orden no pertenece al tenant y unidad activos.")
                if accion == "agregar_item":
                    insumo_id = request.form.get("insumo_id")
                    insumo = modelos["InsumoProductivo"].query.filter_by(
                        id=int(insumo_id), organizacion_id=organizacion.id,
                    ).first() if insumo_id else None
                    if insumo_id and insumo is None:
                        raise ValueError("El insumo no pertenece al tenant activo.")
                    agregar_item_orden(
                        orden, request.form, organizacion_id=organizacion.id,
                        insumo=insumo, OrdenCompraItem=modelos["OrdenCompraItem"],
                        db_session=db.session,
                    )
                    mensaje = f"Ítem agregado a la orden {orden.numero}."
                else:
                    item = next(
                        (fila for fila in orden.items if fila.id == int(request.form.get("item_id"))),
                        None,
                    )
                    if item is None:
                        raise ValueError("El ítem no pertenece a la orden.")
                    quitar_item_orden(
                        orden, item, organizacion_id=organizacion.id,
                        db_session=db.session,
                    )
                    mensaje = f"Ítem quitado de la orden {orden.numero}."
            elif accion == "cambiar_estado":
                orden = modelos["OrdenCompra"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None:
                    raise ValueError("La orden no pertenece al tenant y unidad activos.")
                cambiar_estado_orden(
                    orden, (request.form.get("estado") or "").strip(),
                    organizacion_id=organizacion.id, db_session=db.session,
                )
                mensaje = f"Orden {orden.numero} actualizada a {orden.estado}."
            elif accion == "preparar_recepcion":
                orden = modelos["OrdenCompra"].query.filter_by(
                    id=int(request.form.get("orden_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if orden is None:
                    raise ValueError("La orden no pertenece al tenant y unidad activos.")
                recepcion = preparar_recepcion(
                    request.form, orden=orden, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                    RecepcionCompra=modelos["RecepcionCompra"],
                    RecepcionCompraItem=modelos["RecepcionCompraItem"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Recepción {recepcion.numero} preparada sin impacto en stock o costos."
            elif accion == "preparar_impactos":
                recepcion = modelos["RecepcionCompra"].query.filter_by(
                    id=int(request.form.get("recepcion_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if recepcion is None:
                    raise ValueError("La recepción no pertenece al tenant y unidad activos.")
                creadas = preparar_propuestas(
                    recepcion, organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                    PropuestaImpactoCompra=modelos["PropuestaImpactoCompra"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                    mapeos=modelos["MapeoInsumoInventario"].query.filter_by(
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad.id, activo=True,
                    ).all(),
                )
                mensaje = f"Se prepararon {len(creadas)} propuestas sin ejecutar impactos."
            elif accion == "registrar_factura":
                recepcion = modelos["RecepcionCompra"].query.filter_by(
                    id=int(request.form.get("recepcion_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if recepcion is None:
                    raise ValueError("La recepción no pertenece al tenant y unidad activos.")
                factura = registrar_factura_preparatoria(
                    request.form, recepcion=recepcion,
                    organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    FacturaProveedorCompra=modelos["FacturaProveedorCompra"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Factura {factura.punto_venta}-{factura.numero} registrada como {factura.estado}, sin impacto."
            elif accion == "crear_mapeo_inventario":
                insumo = modelos["InsumoProductivo"].query.filter_by(
                    id=int(request.form.get("insumo_id")), organizacion_id=organizacion.id,
                ).first()
                existencia = modelos["ExistenciaSucursal"].query.filter_by(
                    id=int(request.form.get("existencia_sucursal_id")),
                    organizacion_id=organizacion.id,
                ).first()
                if insumo is None or existencia is None:
                    raise ValueError("El insumo o la existencia no pertenecen al tenant activo.")
                mapeo = crear_mapeo(
                    organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    insumo=insumo, existencia=existencia,
                    MapeoInsumoInventario=modelos["MapeoInsumoInventario"],
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                    observacion=request.form.get("observacion"),
                )
                propuestas = modelos["PropuestaImpactoCompra"].query.filter_by(
                    organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    tipo="stock", estado="bloqueada",
                ).all()
                habilitadas = habilitar_propuestas_stock(
                    propuestas, [mapeo], db_session=db.session,
                )
                mensaje = f"Mapeo creado; {len(habilitadas)} propuestas de stock quedaron preparadas, no ejecutadas."
            elif accion == "decidir_impacto":
                propuesta = modelos["PropuestaImpactoCompra"].query.filter_by(
                    id=int(request.form.get("propuesta_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad.id,
                ).first()
                if propuesta is None:
                    raise ValueError("La propuesta no pertenece al tenant y unidad activos.")
                decidir_propuesta(
                    propuesta, (request.form.get("decision") or "").strip(),
                    request.form.get("motivo"), organizacion_id=organizacion.id,
                    db_session=db.session, usuario_id=getattr(usuario, "id", None),
                )
                mensaje = f"Propuesta #{propuesta.id} actualizada a {propuesta.estado}; ejecución bloqueada."
            else:
                raise ValueError("La acción de compras no es válida.")
            dependencias["registrar_auditoria"](
                f"Compras: {accion}", entidad="compras", detalle=mensaje,
            )
            return redirect(url_for("admin_compras.panel", ok=mensaje))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_compras.panel", error=str(error)))

    @blueprint.route("/admin/compras/control-integral")
    @dependencias["login_required"]
    def control_integral():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_panel_compras(organizacion.id, unidad.id, modelos=modelos)
        resultado = controlar_compras(
            organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
            ordenes=datos["ordenes_compra"], recepciones=datos["recepciones_compra"],
            facturas=datos["facturas_proveedor_compra"],
            mapeos=datos["mapeos_insumo_inventario"],
            propuestas=datos["propuestas_impacto_compra"],
        )
        return send_file(
            exportar_control(resultado), as_attachment=True,
            download_name="control_integral_compras.json", mimetype="application/json",
        )

    return blueprint
