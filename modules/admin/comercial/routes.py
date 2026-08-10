"""Blueprint del panel comercial tenant."""

from flask import Blueprint, redirect, render_template, request, send_file, session, url_for

from services.comercial_admin import procesar_accion_comercial
from services.comercial_consultas import obtener_datos_panel_comercial
from services.fuentes_costo_admin import (
    obtener_fuentes_costo,
    procesar_accion_fuente_costo,
)
from services.importacion_productos_costeo import (
    CAMPOS_PRODUCTOS,
    aplicar_vista_previa,
    deserializar,
    leer_archivo,
    previsualizar,
    serializar,
    sugerir_mapeo,
)
from services.importacion_combos_costeo import (
    CAMPOS_COMBOS,
    aplicar_combos,
    previsualizar_combos,
    sugerir_mapeo_combo,
)
from services.importacion_fuentes_costeo import (
    aplicar_fuentes, aplicar_modo_vista_fuentes,
    definicion as definicion_fuente,
    exportar_excel_tabla, exportar_pdf_tabla, plantilla_excel_fuente,
    presentar_vista_fuentes, previsualizar_fuentes, resumir_vista_fuentes,
    sugerir_mapeo_fuente,
)
from services.fechas import ahora_utc_naive
from services.exportacion_perfiles_costeo import (
    exportar_excel_combos,
    exportar_excel_perfiles,
    exportar_pdf_combos,
    exportar_pdf_perfiles,
    plantilla_excel_combos,
    plantilla_excel_productos,
)
from services.tenant_context import TenantError, resolver_tenant_usuario
from services.unidad_negocio_contexto import (
    UnidadNegocioError,
    resolver_unidad_activa,
)


def crear_blueprint_comercial(*, dependencias):
    blueprint = Blueprint("admin_comercial", __name__)
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
            return None, None, redirect(url_for("inicio", error=str(error)))
        if membresia.rol != "admin":
            return None, None, redirect(url_for("inicio"))
        session["organizacion_id"] = membresia.organizacion_id
        return usuario, membresia.organizacion, None

    def contexto_comercial(organizacion):
        unidad, unidades = resolver_unidad_activa(
            organizacion.id, session.get("unidad_negocio_id"),
            UnidadNegocio=modelos["UnidadNegocio"],
        )
        session["unidad_negocio_id"] = unidad.id
        return unidad, unidades

    @blueprint.route("/admin/comercial/unidad", methods=["POST"])
    @dependencias["login_required"]
    def seleccionar_unidad():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        try:
            unidad_id = int(request.form.get("unidad_negocio_id"))
            unidad = modelos["UnidadNegocio"].query.filter_by(
                id=unidad_id, organizacion_id=organizacion.id, activa=True,
            ).first()
            if unidad is None:
                raise UnidadNegocioError("La unidad no pertenece a la organización.")
            session["unidad_negocio_id"] = unidad.id
        except (TypeError, ValueError, UnidadNegocioError) as error:
            return redirect(url_for("admin_comercial.panel", error=str(error)))
        destino = request.form.get("destino") or "admin_comercial.panel"
        if destino not in {"admin_comercial.panel", "admin_comercial.fuentes_costos"}:
            destino = "admin_comercial.panel"
        return redirect(url_for(destino))

    @blueprint.route("/admin/comercial")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, unidades = contexto_comercial(organizacion)
        return render_template(
            "admin_comercial.html", organizacion=organizacion,
            unidad_activa=unidad_activa, unidades=unidades,
            **obtener_datos_panel_comercial(
                organizacion.id, unidad_activa.id, modelos=modelos,
            ),
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/guardar", methods=["POST"])
    @dependencias["login_required"]
    def guardar():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        accion = (request.form.get("accion") or "").strip()
        try:
            unidad_activa, _unidades = contexto_comercial(organizacion)
            mensaje = procesar_accion_comercial(
                accion, request.form, organizacion=organizacion,
                unidad_activa=unidad_activa,
                modelos=modelos, db_session=db.session, usuario=usuario,
            )
            dependencias["registrar_auditoria"](
                "Configuro administracion comercial",
                entidad="comercial", entidad_id=organizacion.id,
                detalle=f"Accion: {accion}. {mensaje}",
            )
            return redirect(url_for("admin_comercial.panel", ok=mensaje))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.panel", error=str(error)))

    @blueprint.route("/admin/comercial/fuentes-costos")
    @dependencias["login_required"]
    def fuentes_costos():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, unidades = contexto_comercial(organizacion)
        return render_template(
            "admin_fuentes_costos.html",
            organizacion=organizacion,
            unidad_activa=unidad_activa, unidades=unidades,
            **obtener_fuentes_costo(
                organizacion.id, unidad_activa.id, modelos=modelos,
            ),
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route(
        "/admin/comercial/fuentes-costos/guardar",
        methods=["POST"],
    )
    @dependencias["login_required"]
    def guardar_fuente_costo():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        accion = (request.form.get("accion") or "").strip()
        try:
            unidad_activa, _unidades = contexto_comercial(organizacion)
            mensaje = procesar_accion_fuente_costo(
                accion,
                request.form,
                organizacion=organizacion,
                unidad_activa=unidad_activa,
                modelos=modelos,
                db_session=db.session,
                usuario=usuario,
            )
            dependencias["registrar_auditoria"](
                "Configuro fuentes de costo productivo",
                entidad="fuente_costo",
                entidad_id=organizacion.id,
                detalle=f"Accion: {accion}. {mensaje}",
            )
            return redirect(url_for(
                "admin_comercial.fuentes_costos",
                ok=mensaje,
            ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_comercial.fuentes_costos",
                error=str(error),
            ))

    @blueprint.route(
        "/admin/comercial/importaciones/productos",
        methods=["GET", "POST"],
    )
    @dependencias["login_required"]
    def importar_productos_costeo():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        Lote = modelos["ImportacionMasivaCosto"]
        unidad_activa, unidades = contexto_comercial(organizacion)
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename:
                        raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo, request.form.get("hoja"))
                    lote = Lote(
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        usuario_id=getattr(usuario, "id", None),
                        tipo_datos="productos_clasificacion",
                        nombre_archivo=archivo.filename,
                        nombre_hoja=lectura["hoja"],
                        encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(sugerir_mapeo(lectura["encabezados"])),
                        total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote)
                    db.session.commit()
                    return redirect(url_for(
                        "admin_comercial.importar_productos_costeo", lote=lote.id,
                    ))
                lote = Lote.query.filter_by(
                    id=int(request.form.get("lote_id")),
                    organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad_activa.id,
                ).first()
                if lote is None:
                    raise ValueError("El lote no existe.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {
                        str(i): (
                            (request.form.get(f"col_{i}") or "").strip()
                            if request.form.get(f"usar_{i}") == "1"
                            else ""
                        )
                        for i in range(len(encabezados))
                    }
                    vista = previsualizar(
                        deserializar(lote.filas_json, []), mapeo,
                        organizacion_id=organizacion.id, modelos=modelos,
                        unidad_negocio_id=unidad_activa.id,
                    )
                    lote.modo = (request.form.get("modo") or "crear_actualizar").strip()
                    if lote.modo not in {"crear", "actualizar", "crear_actualizar", "validar"}:
                        raise ValueError("El modo de importacion no es valido.")
                    for fila in vista:
                        if lote.modo == "crear" and fila["accion"] == "actualizar":
                            fila["accion"] = "rechazado"
                            fila["errores"].append("El modo solo permite crear")
                        elif lote.modo == "actualizar" and fila["accion"] == "crear":
                            fila["accion"] = "rechazado"
                            fila["errores"].append("El modo solo permite actualizar")
                    lote.mapeo_json = serializar(mapeo)
                    lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"
                    db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado":
                        raise ValueError("Primero validá el mapeo.")
                    if lote.modo == "validar":
                        raise ValueError("El modo solo validar no permite confirmar.")
                    conteos = aplicar_vista_previa(
                        deserializar(lote.vista_previa_json, []),
                        organizacion_id=organizacion.id,
                        modelos=modelos, db_session=db.session,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items():
                        setattr(lote, campo, valor)
                    lote.estado = "confirmado"
                    lote.fecha_confirmacion = ahora_utc_naive()
                    db.session.commit()
                return redirect(url_for(
                    "admin_comercial.importar_productos_costeo", lote=lote.id,
                ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_comercial.importar_productos_costeo", error=str(error),
            ))

        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(
            id=lote_id, organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
        ).first() if lote_id else None
        return render_template(
            "admin_importacion_productos_costeo.html",
            organizacion=organizacion, unidad_activa=unidad_activa, lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=deserializar(lote.vista_previa_json, []) if lote else [],
            campos=CAMPOS_PRODUCTOS,
            historial=Lote.query.filter_by(
                organizacion_id=organizacion.id,
                unidad_negocio_id=unidad_activa.id,
                tipo_datos="productos_clasificacion",
            ).order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/importaciones/productos/plantilla")
    @dependencias["login_required"]
    def plantilla_productos_costeo():
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        return send_file(
            plantilla_excel_productos(), as_attachment=True,
            download_name="plantilla_productos_clasificacion.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @blueprint.route("/admin/comercial/exportaciones/productos/<formato>")
    @dependencias["login_required"]
    def exportar_productos_costeo(formato):
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        perfiles = modelos["PerfilCosteoProducto"].query.filter_by(
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
        ).order_by(modelos["PerfilCosteoProducto"].fecha_creacion).all()
        if formato == "xlsx":
            return send_file(
                exportar_excel_perfiles(perfiles), as_attachment=True,
                download_name="productos_clasificacion.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        if formato == "pdf":
            return send_file(
                exportar_pdf_perfiles(perfiles, unidad_activa.nombre),
                as_attachment=True, download_name="productos_clasificacion.pdf",
                mimetype="application/pdf",
            )
        raise ValueError("Formato de exportacion no valido.")

    @blueprint.route("/admin/comercial/importaciones/combos", methods=["GET", "POST"])
    @dependencias["login_required"]
    def importar_combos_costeo():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        Lote = modelos["ImportacionMasivaCosto"]
        unidad_activa, unidades = contexto_comercial(organizacion)
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename:
                        raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo)
                    lote = Lote(
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        usuario_id=getattr(usuario, "id", None),
                        tipo_datos="componentes_combos", nombre_archivo=archivo.filename,
                        modo=(request.form.get("modo") or "crear_actualizar").strip(),
                        nombre_hoja=lectura["hoja"], estado="cargado",
                        encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(sugerir_mapeo_combo(lectura["encabezados"])),
                        total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote); db.session.commit()
                    return redirect(url_for("admin_comercial.importar_combos_costeo", lote=lote.id))
                lote = Lote.query.filter_by(
                    id=int(request.form.get("lote_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad_activa.id,
                    tipo_datos="componentes_combos",
                ).first()
                if lote is None:
                    raise ValueError("El lote no existe.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {str(i): ((request.form.get(f"col_{i}") or "").strip() if request.form.get(f"usar_{i}") == "1" else "") for i in range(len(encabezados))}
                    vista = previsualizar_combos(
                        deserializar(lote.filas_json, []), mapeo,
                        organizacion_id=organizacion.id, modelos=modelos, modo=lote.modo,
                        unidad_negocio_id=unidad_activa.id,
                    )
                    lote.mapeo_json, lote.vista_previa_json = serializar(mapeo), serializar(vista)
                    lote.estado = "mapeado"; db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado":
                        raise ValueError("Primero validá el mapeo.")
                    if lote.modo == "solo_validar":
                        raise ValueError("El modo Solo validar no permite confirmar cambios.")
                    conteos = aplicar_combos(
                        deserializar(lote.vista_previa_json, []), modelos=modelos,
                        db_session=db.session,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items(): setattr(lote, campo, valor)
                    lote.estado, lote.fecha_confirmacion = "confirmado", ahora_utc_naive()
                    db.session.commit()
                return redirect(url_for("admin_comercial.importar_combos_costeo", lote=lote.id))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.importar_combos_costeo", error=str(error)))
        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(id=lote_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos="componentes_combos").first() if lote_id else None
        return render_template(
            "admin_importacion_combos.html", organizacion=organizacion,
            unidad_activa=unidad_activa, lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=deserializar(lote.vista_previa_json, []) if lote else [], campos=CAMPOS_COMBOS,
            historial=Lote.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos="componentes_combos").order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/importaciones/combos/plantilla")
    @dependencias["login_required"]
    def plantilla_combos_costeo():
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        return send_file(plantilla_excel_combos(), as_attachment=True, download_name="plantilla_componentes_combos.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @blueprint.route("/admin/comercial/exportaciones/combos/<formato>")
    @dependencias["login_required"]
    def exportar_combos_costeo(formato):
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        combos = modelos["PerfilCosteoProducto"].query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo="combo").all()
        if formato == "xlsx":
            return send_file(exportar_excel_combos(combos), as_attachment=True, download_name="componentes_combos.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if formato == "pdf":
            return send_file(exportar_pdf_combos(combos, unidad_activa.nombre), as_attachment=True, download_name="componentes_combos.pdf", mimetype="application/pdf")
        raise ValueError("Formato de exportacion no valido.")

    @blueprint.route("/admin/comercial/importaciones/fuentes/<tipo>", methods=["GET", "POST"])
    @dependencias["login_required"]
    def importar_fuente_costeo(tipo):
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        config = definicion_fuente(tipo); Lote = modelos["ImportacionMasivaCosto"]
        tipo_lote = f"fuente_{tipo}"
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename: raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo)
                    lote = Lote(
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                        usuario_id=getattr(usuario, "id", None), tipo_datos=tipo_lote,
                        nombre_archivo=archivo.filename, nombre_hoja=lectura["hoja"],
                        estado="cargado", modo=(request.form.get("modo") or "crear_actualizar"),
                        encabezados_json=serializar(lectura["encabezados"]), filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(sugerir_mapeo_fuente(tipo, lectura["encabezados"])), total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote); db.session.commit()
                    return redirect(url_for("admin_comercial.importar_fuente_costeo", tipo=tipo, lote=lote.id))
                lote = Lote.query.filter_by(id=int(request.form.get("lote_id")), organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).first()
                if lote is None: raise ValueError("El lote no existe en la unidad activa.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {str(i): ((request.form.get(f"col_{i}") or "").strip() if request.form.get(f"usar_{i}") == "1" else "") for i in range(len(encabezados))}
                    vista = previsualizar_fuentes(tipo, deserializar(lote.filas_json, []), mapeo, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, modelos=modelos)
                    vista = aplicar_modo_vista_fuentes(vista, lote.modo)
                    lote.mapeo_json, lote.vista_previa_json, lote.estado = serializar(mapeo), serializar(vista), "mapeado"; db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado" or lote.modo == "solo_validar": raise ValueError("El lote no admite confirmación.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = previsualizar_fuentes(
                        tipo, deserializar(lote.filas_json, []),
                        deserializar(lote.mapeo_json, {}),
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                    )
                    vista_actual = aplicar_modo_vista_fuentes(vista_actual, lote.modo)
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual)
                        db.session.commit()
                        return redirect(url_for(
                            "admin_comercial.importar_fuente_costeo",
                            tipo=tipo, lote=lote.id,
                            error="Los datos cambiaron desde la validación. Revisá la vista actualizada y confirmá nuevamente.",
                        ))
                    resumen_confirmacion = resumir_vista_fuentes(vista_actual)
                    if not resumen_confirmacion["aplicables"]:
                        raise ValueError("El lote no contiene filas aplicables.")
                    conteos = aplicar_fuentes(tipo, vista_actual, organizacion=organizacion, unidad_activa=unidad_activa, modelos=modelos, db_session=db.session, usuario=usuario)
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items(): setattr(lote, campo, valor)
                    lote.estado, lote.fecha_confirmacion = "confirmado", ahora_utc_naive(); db.session.commit()
                    dependencias["registrar_auditoria"](
                        "Confirmó importación productiva",
                        entidad="importacion_masiva_costo",
                        entidad_id=lote.id,
                        detalle=(
                            f"Unidad {unidad_activa.id}; tipo {tipo}; "
                            f"{conteos['creados']} creados; "
                            f"{conteos['actualizados']} actualizados; "
                            f"{conteos['rechazados']} rechazados."
                        ),
                    )
                return redirect(url_for("admin_comercial.importar_fuente_costeo", tipo=tipo, lote=lote.id))
        except Exception as error:
            db.session.rollback(); return redirect(url_for("admin_comercial.importar_fuente_costeo", tipo=tipo, error=str(error)))
        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(id=lote_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).first() if lote_id else None
        vista = deserializar(lote.vista_previa_json, []) if lote else []
        columnas_vista, vista_presentada = presentar_vista_fuentes(tipo, vista)
        resumen_vista = resumir_vista_fuentes(vista)
        mostrar_configuracion = not vista or request.args.get("configurar") == "1"
        return render_template("admin_importacion_fuentes_costeo.html", tipo=tipo, config=config, unidad_activa=unidad_activa, lote=lote, encabezados=deserializar(lote.encabezados_json, []) if lote else [], filas=deserializar(lote.filas_json, []) if lote else [], mapeo=deserializar(lote.mapeo_json, {}) if lote else {}, vista=vista, columnas_vista=columnas_vista, vista_presentada=vista_presentada, resumen_vista=resumen_vista, mostrar_configuracion=mostrar_configuracion, historial=Lote.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).order_by(Lote.fecha_creacion.desc()).limit(20).all(), error=(request.args.get("error") or "").strip())

    @blueprint.route("/admin/comercial/importaciones/fuentes/<tipo>/plantilla")
    @dependencias["login_required"]
    def plantilla_fuente_costeo(tipo):
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        definicion_fuente(tipo)
        return send_file(plantilla_excel_fuente(tipo), as_attachment=True, download_name=f"plantilla_{tipo}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @blueprint.route("/admin/comercial/exportaciones/fuentes/<tipo>/<formato>")
    @dependencias["login_required"]
    def exportar_fuente_costeo(tipo, formato):
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad, _unidades = contexto_comercial(organizacion); config = definicion_fuente(tipo)
        filas = []
        encabezados = [nombre.upper() for nombre, _obligatorio in config["campos"].values()]
        if tipo == "insumos":
            registros = obtener_fuentes_costo(organizacion.id, unidad.id, modelos=modelos)["insumos"]
            for r in registros:
                v = next((x for x in r.versiones_precio if x.vigente), None)
                filas.append([r.codigo, r.nombre, r.tipo, r.unidad_medida, v.precio_unitario_centavos / 100 if v else "", v.proveedor_referencia if v else ""])
        elif tipo == "empleados":
            registros = obtener_fuentes_costo(organizacion.id, unidad.id, modelos=modelos)["empleados"]
            for r in registros:
                v = next((x for x in r.versiones_costo if x.vigente), None)
                filas.append([
                    r.codigo, r.nombre, r.sector, r.puesto or "",
                    v.sueldo_base_centavos / 100 if v else "",
                    "" if v and v.usa_porcentaje_general else v.porcentaje_cargas if v else "",
                    v.adicionales_centavos / 100 if v else "",
                    v.otros_costos_centavos / 100 if v else "",
                    v.horas_mensuales if v else "", v.horas_productivas if v else "",
                ])
        elif tipo == "recursos":
            registros = obtener_fuentes_costo(
                organizacion.id, unidad.id, modelos=modelos,
            )["recursos_productivos"]
            for recurso in registros:
                for vinculo in recurso.miembros_recurso:
                    filas.append([
                        recurso.codigo, recurso.nombre, recurso.sector,
                        recurso.porcentaje_indirecto,
                        vinculo.empleado.codigo, vinculo.porcentaje_dedicacion,
                    ])
        elif tipo == "costos-fijos":
            registros = obtener_fuentes_costo(organizacion.id, unidad.id, modelos=modelos)["costos_fijos"]
            for r in registros:
                v = next((x for x in r.versiones if x.vigente), None)
                filas.append([
                    r.codigo, r.nombre, r.categoria,
                    "si" if r.integra_costo_produccion else "no",
                    r.criterio_distribucion,
                    v.importe_mensual_centavos / 100 if v else "",
                    v.comprobante_referencia if v else "",
                ])
        else:
            registros = obtener_fuentes_costo(organizacion.id, unidad.id, modelos=modelos)["perfiles_produccion"]
            for p in registros:
                filas += [[p.producto.sku, "insumo", x.insumo.codigo, x.cantidad, x.porcentaje_merma, "", "", "", ""] for x in p.insumos_costeo]
                filas += [[p.producto.sku, "operacion", x.empleado.codigo, "", "", x.nombre, x.minutos, "", ""] for x in p.operaciones_costeo]
                filas += [[p.producto.sku, "costo_fijo", x.costo_fijo.codigo, "", "", "", "", x.porcentaje_asignacion, x.unidades_mensuales] for x in p.costos_fijos_costeo]
        salida = exportar_excel_tabla(config["titulo"], encabezados, filas) if formato == "xlsx" else exportar_pdf_tabla(config["titulo"], unidad.nombre, encabezados, filas) if formato == "pdf" else None
        if salida is None: raise ValueError("Formato no válido.")
        return send_file(salida, as_attachment=True, download_name=f"{tipo}.{formato}", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if formato == "xlsx" else "application/pdf")

    return blueprint
