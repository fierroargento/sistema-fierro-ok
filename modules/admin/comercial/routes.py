"""Blueprint del panel comercial tenant."""

from flask import Blueprint, redirect, render_template, request, send_file, session, url_for

from services.comercial_admin import procesar_accion_comercial
from services.comercial_consultas import obtener_datos_panel_comercial
from services.control_comercial_masivo import exportar_bandeja_excel
from services.catalogos_comerciales import importe_a_centavos
from services.conciliacion_liquidaciones_canal import (
    construir_conciliaciones, exportar_conciliaciones, incorporar_gestiones,
    registrar_gestion, registrar_movimiento, registrar_venta,
)
from services.importacion_conciliacion_canal import (
    aplicar as aplicar_importacion_conciliacion,
    campos_para as campos_importacion_conciliacion,
    plantilla as plantilla_importacion_conciliacion,
    previsualizar_movimientos,
    previsualizar_ventas,
    sugerir_mapeo as sugerir_mapeo_conciliacion,
)
from services.simulador_integral_comercial import ESCENARIOS, escenario_predefinido, simular_escenario
from services.cola_acciones_comerciales import crear_propuestas, decidir_propuesta
from services.fuentes_costo_admin import (
    obtener_fuentes_costo,
    procesar_accion_fuente_costo,
)
from services.importacion_productos_costeo import (
    CAMPOS_PRODUCTOS,
    aplicar_modo_productos,
    aplicar_vista_previa,
    deserializar,
    leer_archivo,
    previsualizar,
    serializar,
    sugerir_mapeo,
)
from services.importacion_inclusiones_catalogo import (
    CAMPOS_INCLUSIONES,
    aplicar_inclusiones,
    aplicar_modo_inclusiones,
    plantilla_inclusiones_catalogo,
    previsualizar_inclusiones,
    sugerir_mapeo_inclusiones,
)
from services.importacion_logistica_catalogo import (
    CAMPOS_LOGISTICA,
    aplicar_logistica,
    plantilla_logistica_catalogo,
    previsualizar_logistica,
    sugerir_mapeo_logistica,
)
from services.importacion_datos_comerciales_canal import (
    aplicar as aplicar_datos_canal,
    campos_para as campos_datos_canal,
    plantilla as plantilla_datos_canal,
    previsualizar as previsualizar_datos_canal,
    sugerir_mapeo as sugerir_mapeo_datos_canal,
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
from services.presentacion_monetaria import formatear_centavos_ars
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
        if destino not in {"admin_comercial.panel", "admin_comercial.fuentes_costos", "admin_comercial.cuentas_pagar"}:
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
                archivos=request.files,
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
            formatear_centavos_ars=formatear_centavos_ars,
            **obtener_fuentes_costo(
                organizacion.id, unidad_activa.id, modelos=modelos,
            ),
            ok_feedback=(request.args.get("ok") or "").strip(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/conciliacion/importar/<tipo>", methods=["GET", "POST"])
    @dependencias["login_required"]
    def importar_conciliacion_canal(tipo):
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        campos = campos_importacion_conciliacion(tipo); Lote = modelos["ImportacionMasivaCosto"]
        tipo_lote = f"conciliacion_{tipo}"
        def generar_vista(lote):
            funcion = previsualizar_ventas if tipo == "ventas" else previsualizar_movimientos
            return funcion(deserializar(lote.filas_json, []), deserializar(lote.mapeo_json, {}), organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, modelos=modelos)
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename: raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo, request.form.get("hoja"))
                    lote = Lote(
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                        usuario_id=getattr(usuario, "id", None), tipo_datos=tipo_lote,
                        nombre_archivo=archivo.filename, nombre_hoja=lectura["hoja"], estado="cargado",
                        modo="crear_observaciones", encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(sugerir_mapeo_conciliacion(lectura["encabezados"], tipo)),
                        total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote); db.session.commit()
                    return redirect(url_for("admin_comercial.importar_conciliacion_canal", tipo=tipo, lote=lote.id))
                lote = Lote.query.filter_by(id=int(request.form.get("lote_id")), organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).first()
                if lote is None: raise ValueError("El lote no existe en la unidad activa.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    lote.mapeo_json = serializar({str(i): ((request.form.get(f"col_{i}") or "").strip() if request.form.get(f"usar_{i}") == "1" else "") for i in range(len(encabezados))})
                    lote.vista_previa_json = serializar(generar_vista(lote)); lote.estado = "mapeado"; db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado": raise ValueError("Primero validá el mapeo.")
                    vista_guardada = deserializar(lote.vista_previa_json, []); vista_actual = generar_vista(lote)
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual); db.session.commit()
                        return redirect(url_for("admin_comercial.importar_conciliacion_canal", tipo=tipo, lote=lote.id, error="Los datos internos cambiaron. Revisá y confirmá nuevamente."))
                    if not any(fila["accion"] == "crear" for fila in vista_actual): raise ValueError("El lote no contiene filas aplicables.")
                    conteos = aplicar_importacion_conciliacion(vista_actual, tipo, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, usuario=usuario, modelos=modelos, db_session=db.session)
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items(): setattr(lote, campo, valor)
                    lote.estado = "confirmado"; lote.fecha_confirmacion = ahora_utc_naive(); db.session.commit()
                    dependencias["registrar_auditoria"]("Importó datos internos de conciliación", entidad="importacion_masiva_costo", entidad_id=lote.id, detalle=f"Tipo {tipo}; {conteos['creados']} creados; {conteos['rechazados']} rechazados.")
                return redirect(url_for("admin_comercial.importar_conciliacion_canal", tipo=tipo, lote=lote.id))
        except Exception as error:
            db.session.rollback(); return redirect(url_for("admin_comercial.importar_conciliacion_canal", tipo=tipo, error=str(error)))
        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(id=lote_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).first() if lote_id else None
        return render_template(
            "admin_importacion_conciliacion.html", organizacion=organizacion, unidad_activa=unidad_activa,
            tipo=tipo, campos=campos, lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [], filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {}, vista=deserializar(lote.vista_previa_json, []) if lote else [],
            historial=Lote.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/conciliacion/importar/<tipo>/plantilla")
    @dependencias["login_required"]
    def plantilla_conciliacion_canal(tipo):
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        campos_importacion_conciliacion(tipo)
        return send_file(plantilla_importacion_conciliacion(tipo), as_attachment=True, download_name=f"plantilla_conciliacion_{tipo}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @blueprint.route("/admin/comercial/conciliacion/exportar")
    @dependencias["login_required"]
    def exportar_conciliacion_canal():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        ventas = modelos["VentaCanalItem"].query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).all()
        movimientos = modelos["MovimientoLiquidacionCanal"].query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).all()
        gestiones = modelos["GestionConciliacionCanal"].query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).all()
        filas, _resumen = construir_conciliaciones(ventas, movimientos)
        incorporar_gestiones(filas, gestiones)
        return send_file(exportar_conciliaciones(filas), as_attachment=True, download_name="conciliacion_liquidaciones.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @blueprint.route("/admin/comercial/simulador-integral", methods=["GET", "POST"])
    @dependencias["login_required"]
    def simulador_integral_comercial():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, unidades = contexto_comercial(organizacion)
        clave = (request.values.get("escenario") or "promocion").strip()
        try:
            datos = escenario_predefinido(clave)
            if request.method == "POST" and request.form.get("modo") == "personalizado":
                datos = {
                    "nombre": "Escenario personalizado",
                    "costo_centavos": importe_a_centavos(request.form.get("costo")),
                    "impuesto_pct": request.form.get("impuesto_pct"),
                    "utilidad_pct": request.form.get("utilidad_pct"),
                    "precio_final_centavos": importe_a_centavos(request.form.get("precio_final")),
                    "comision_pct": request.form.get("comision_pct"),
                    "cargo_fijo_centavos": importe_a_centavos(request.form.get("cargo_fijo")),
                    "umbral_envio_centavos": importe_a_centavos(request.form.get("umbral_envio")),
                    "envio_centavos": importe_a_centavos(request.form.get("envio")),
                    "promocion_activa": request.form.get("promocion_activa") == "1",
                    "descuento_pct": request.form.get("descuento_pct"),
                    "liquidacion_real_centavos": importe_a_centavos(request.form.get("liquidacion_real")),
                    "estado_venta": request.form.get("estado_venta"),
                    "redondeo_centavos": 100,
                }
            resultado = simular_escenario(datos)
            error = ""
        except Exception as excepcion:
            resultado = None; error = str(excepcion)
            datos = locals().get("datos", escenario_predefinido("promocion"))
        return render_template(
            "admin_simulador_integral_comercial.html", organizacion=organizacion,
            unidad_activa=unidad_activa, unidades=unidades, escenarios=ESCENARIOS,
            escenario_activo=clave, datos=datos, resultado=resultado, error=error,
        )

    @blueprint.route("/admin/comercial/conciliacion", methods=["GET", "POST"])
    @dependencias["login_required"]
    def conciliacion_canal():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, unidades = contexto_comercial(organizacion)
        Venta = modelos["VentaCanalItem"]; Movimiento = modelos["MovimientoLiquidacionCanal"]
        Gestion = modelos["GestionConciliacionCanal"]
        Lista = modelos["ListaPrecio"]; Inclusion = modelos["CatalogoProducto"]
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "registrar_venta":
                    lista = Lista.query.filter_by(id=int(request.form.get("lista_precio_id")), organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).first()
                    inclusion = Inclusion.query.get(int(request.form.get("catalogo_producto_id")))
                    if lista is None or inclusion is None or inclusion.catalogo.organizacion_id != organizacion.id or inclusion.catalogo.unidad_negocio_id != unidad_activa.id: raise ValueError("La lista o el producto no pertenecen a la unidad activa.")
                    regla = modelos["ReglaCanalVersion"].query.filter_by(lista_precio_id=lista.id, vigente=True).first()
                    if regla is None: raise ValueError("La lista no tiene una politica de canal vigente.")
                    datos_panel = obtener_datos_panel_comercial(organizacion.id, unidad_activa.id, modelos=modelos)
                    control = next((fila for fila in datos_panel["control_comercial"] if fila.get("inclusion") is not None and fila["inclusion"].id == inclusion.id and fila["regla_canal"].lista_precio_id == lista.id), None)
                    registrar_venta(
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                        lista_precio_id=lista.id, catalogo_producto_id=inclusion.id,
                        cuenta_codigo=request.form.get("cuenta_codigo"), referencia_venta=request.form.get("referencia_venta"),
                        referencia_item=request.form.get("referencia_item"), referencia_pago=request.form.get("referencia_pago"),
                        cantidad=int(request.form.get("cantidad")), precio_unitario_centavos=importe_a_centavos(request.form.get("precio_unitario")),
                        estado=request.form.get("estado"), fecha_venta=ahora_utc_naive(), regla_canal=regla,
                        costo_unitario_centavos=getattr(control.get("costo"), "costo_total_centavos", None) if control else None,
                        piso_unitario_centavos=control["minimo"]["piso_liquidacion_centavos"] if control else None,
                        usuario=usuario, VentaCanalItem=Venta, db_session=db.session,
                    )
                    mensaje = "Venta observada registrada."
                elif accion == "registrar_movimiento":
                    registrar_movimiento(
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                        cuenta_codigo=request.form.get("cuenta_codigo"), referencia_venta=request.form.get("referencia_venta"),
                        referencia_pago=request.form.get("referencia_pago"), referencia_movimiento=request.form.get("referencia_movimiento"),
                        tipo=request.form.get("tipo"), direccion=request.form.get("direccion"),
                        importe_centavos=importe_a_centavos(request.form.get("importe")), fecha_movimiento=ahora_utc_naive(),
                        impacta_saldo=request.form.get("impacta_saldo") == "1", detalle=request.form.get("detalle"),
                        usuario=usuario, MovimientoLiquidacionCanal=Movimiento, db_session=db.session,
                    )
                    mensaje = "Movimiento de liquidacion registrado."
                elif accion == "gestionar_casos":
                    ventas_actuales = Venta.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).all()
                    movimientos_actuales = Movimiento.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).all()
                    filas_actuales, _ = construir_conciliaciones(ventas_actuales, movimientos_actuales)
                    por_clave = {f'{fila["cuenta_codigo"]}|||{fila["referencia_venta"]}': fila for fila in filas_actuales}
                    seleccion = request.form.getlist("casos")
                    if not seleccion: raise ValueError("Selecciona al menos un caso de conciliacion.")
                    for clave in seleccion:
                        fila = por_clave.get(clave)
                        if fila is None: raise ValueError("Una conciliacion seleccionada ya no existe.")
                        registrar_gestion(
                            fila, clasificacion=request.form.get("clasificacion"),
                            estado=request.form.get("estado_gestion"), observacion=request.form.get("observacion"),
                            organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                            usuario=usuario, GestionConciliacionCanal=Gestion,
                            db_session=db.session, commit=False,
                        )
                    db.session.commit()
                    mensaje = f"Se registraron {len(seleccion)} decisiones de conciliacion."
                else: raise ValueError("La accion de conciliacion no es valida.")
                dependencias["registrar_auditoria"]("Registro conciliacion comercial", entidad="conciliacion_canal", entidad_id=organizacion.id, detalle=mensaje)
                return redirect(url_for("admin_comercial.conciliacion_canal", ok=mensaje))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.conciliacion_canal", error=str(error)))
        ventas = Venta.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).order_by(Venta.fecha_venta.desc()).all()
        movimientos = Movimiento.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).order_by(Movimiento.fecha_movimiento.desc()).all()
        gestiones = Gestion.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).order_by(Gestion.fecha_registro.desc()).all()
        conciliaciones, resumen = construir_conciliaciones(ventas, movimientos)
        incorporar_gestiones(conciliaciones, gestiones)
        filtro = (request.args.get("filtro") or "todos").strip().lower()
        if filtro == "requieren_revision": conciliaciones = [fila for fila in conciliaciones if fila["requiere_revision"] and fila["estado_gestion"] not in {"resuelta", "descartada"}]
        elif filtro == "abiertas": conciliaciones = [fila for fila in conciliaciones if fila["estado_gestion"] in {"abierta", "en_revision"}]
        elif filtro == "cerradas": conciliaciones = [fila for fila in conciliaciones if fila["estado_gestion"] in {"resuelta", "descartada"}]
        return render_template(
            "admin_conciliacion_canal.html", organizacion=organizacion,
            unidad_activa=unidad_activa, unidades=unidades, ventas=ventas,
            movimientos=movimientos, conciliaciones=conciliaciones,
            resumen_conciliacion=resumen, gestiones=gestiones, filtro=filtro,
            listas=Lista.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id).order_by(Lista.nombre).all(),
            inclusiones=Inclusion.query.join(modelos["Catalogo"]).filter(modelos["Catalogo"].organizacion_id == organizacion.id, modelos["Catalogo"].unidad_negocio_id == unidad_activa.id).order_by(Inclusion.nombre_comercial).all(),
            ok_feedback=(request.args.get("ok") or "").strip(), error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/control-comercial/exportar", methods=["GET", "POST"])
    @dependencias["login_required"]
    def exportar_control_comercial():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        datos = obtener_datos_panel_comercial(
            organizacion.id, unidad_activa.id, modelos=modelos,
        )
        filas = datos["control_comercial"]
        seleccion = set(request.form.getlist("claves")) if request.method == "POST" else set()
        if seleccion:
            filas = [fila for fila in filas if fila["clave"] in seleccion]
        if not filas:
            raise ValueError("No hay filas de control para exportar.")
        return send_file(
            exportar_bandeja_excel(filas), as_attachment=True,
            download_name="control_comercial.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @blueprint.route("/admin/comercial/control-comercial/proponer", methods=["POST"])
    @dependencias["login_required"]
    def proponer_acciones_comerciales():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        try:
            unidad_activa, _unidades = contexto_comercial(organizacion)
            seleccion = set(request.form.getlist("claves"))
            if not seleccion: raise ValueError("Seleccioná al menos un producto.")
            datos = obtener_datos_panel_comercial(organizacion.id, unidad_activa.id, modelos=modelos)
            filas = [fila for fila in datos["control_comercial"] if fila["clave"] in seleccion]
            resultado = crear_propuestas(
                filas, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                usuario=usuario, PropuestaAccionComercial=modelos["PropuestaAccionComercial"],
                db_session=db.session,
            )
            mensaje = f'{len(resultado["creadas"])} propuestas creadas; {resultado["omitidas"]} duplicadas omitidas.'
            dependencias["registrar_auditoria"]("Preparo acciones comerciales internas", entidad="comercial", entidad_id=organizacion.id, detalle=mensaje)
            return redirect(url_for("admin_comercial.panel", ok=mensaje) + "#cola-comercial")
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.panel", error=str(error)) + "#control-comercial")

    @blueprint.route("/admin/comercial/control-comercial/decidir", methods=["POST"])
    @dependencias["login_required"]
    def decidir_accion_comercial():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        try:
            unidad_activa, _unidades = contexto_comercial(organizacion)
            propuesta = modelos["PropuestaAccionComercial"].query.filter_by(
                id=int(request.form.get("propuesta_id")), organizacion_id=organizacion.id,
                unidad_negocio_id=unidad_activa.id,
            ).first()
            datos = obtener_datos_panel_comercial(organizacion.id, unidad_activa.id, modelos=modelos)
            fila_actual = next((fila for fila in datos["control_comercial"] if propuesta is not None and fila["regla_canal"].lista_precio_id == propuesta.lista_precio_id and fila.get("inclusion") is not None and fila["inclusion"].id == propuesta.catalogo_producto_id), None)
            propuesta = decidir_propuesta(
                propuesta, request.form.get("decision"), request.form.get("motivo"),
                usuario=usuario, db_session=db.session, fila_actual=fila_actual,
            )
            mensaje = f"Propuesta {propuesta.id} actualizada a {propuesta.estado}."
            dependencias["registrar_auditoria"]("Decidio accion comercial interna", entidad="propuesta_accion_comercial", entidad_id=propuesta.id, detalle=mensaje)
            return redirect(url_for("admin_comercial.panel", ok=mensaje) + "#cola-comercial")
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.panel", error=str(error)) + "#cola-comercial")

    @blueprint.route("/admin/comercial/cuentas-pagar")
    @dependencias["login_required"]
    def cuentas_pagar():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, unidades = contexto_comercial(organizacion)
        return render_template(
            "admin_cuentas_pagar.html",
            organizacion=organizacion,
            unidad_activa=unidad_activa, unidades=unidades,
            formatear_centavos_ars=formatear_centavos_ars,
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
                archivos=request.files,
            )
            dependencias["registrar_auditoria"](
                "Configuro fuentes de costo productivo",
                entidad="fuente_costo",
                entidad_id=organizacion.id,
                detalle=f"Accion: {accion}. {mensaje}",
            )
            destino = (request.form.get("destino") or "fuentes").strip()
            endpoint = "admin_comercial.cuentas_pagar" if destino == "cuentas_pagar" else "admin_comercial.fuentes_costos"
            return redirect(url_for(endpoint, ok=mensaje))
        except Exception as error:
            db.session.rollback()
            destino = (request.form.get("destino") or "fuentes").strip()
            endpoint = "admin_comercial.cuentas_pagar" if destino == "cuentas_pagar" else "admin_comercial.fuentes_costos"
            return redirect(url_for(endpoint, error=str(error)))

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
                        modo="crear_actualizar",
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
                    tipo_datos="productos_clasificacion",
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
                    vista = aplicar_modo_productos(vista, lote.modo)
                    lote.mapeo_json = serializar(mapeo)
                    lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"
                    db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado":
                        raise ValueError("Primero validá el mapeo.")
                    if lote.modo == "validar":
                        raise ValueError("El modo solo validar no permite confirmar.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = previsualizar(
                        deserializar(lote.filas_json, []),
                        deserializar(lote.mapeo_json, {}),
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                    )
                    vista_actual = aplicar_modo_productos(
                        vista_actual, lote.modo
                    )
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual)
                        db.session.commit()
                        return redirect(url_for(
                            "admin_comercial.importar_productos_costeo",
                            lote=lote.id,
                            error=(
                                "Los datos cambiaron desde la validacion. "
                                "Revisa la vista y confirma nuevamente."
                            ),
                        ))
                    conteos = aplicar_vista_previa(
                        vista_actual,
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos, db_session=db.session,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items():
                        setattr(lote, campo, valor)
                    lote.estado = "confirmado"
                    lote.fecha_confirmacion = ahora_utc_naive()
                    db.session.commit()
                    dependencias["registrar_auditoria"](
                        "Confirmó importación de clasificación de productos",
                        entidad="importacion_masiva_costo",
                        entidad_id=lote.id,
                        detalle=(
                            f"Unidad {unidad_activa.id}; "
                            f"{conteos['creados']} creados; "
                            f"{conteos['actualizados']} actualizados; "
                            f"{conteos['rechazados']} rechazados."
                        ),
                    )
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
            tipo_datos="productos_clasificacion",
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

    @blueprint.route(
        "/admin/comercial/importaciones/inclusiones-catalogo",
        methods=["GET", "POST"],
    )
    @dependencias["login_required"]
    def importar_inclusiones_catalogo():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        Lote = modelos["ImportacionMasivaCosto"]
        tipo_lote = "inclusiones_catalogo"
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
                        tipo_datos=tipo_lote,
                        nombre_archivo=archivo.filename,
                        nombre_hoja=lectura["hoja"],
                        estado="cargado",
                        modo=(request.form.get("modo") or "crear_actualizar"),
                        encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(
                            sugerir_mapeo_inclusiones(lectura["encabezados"])
                        ),
                        total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote)
                    db.session.commit()
                    return redirect(url_for(
                        "admin_comercial.importar_inclusiones_catalogo",
                        lote=lote.id,
                    ))
                lote = Lote.query.filter_by(
                    id=int(request.form.get("lote_id")),
                    organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad_activa.id,
                    tipo_datos=tipo_lote,
                ).first()
                if lote is None:
                    raise ValueError("El lote no existe en la unidad activa.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {
                        str(i): (
                            (request.form.get(f"col_{i}") or "").strip()
                            if request.form.get(f"usar_{i}") == "1" else ""
                        )
                        for i in range(len(encabezados))
                    }
                    vista = previsualizar_inclusiones(
                        deserializar(lote.filas_json, []), mapeo,
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                    )
                    vista = aplicar_modo_inclusiones(vista, lote.modo)
                    lote.mapeo_json = serializar(mapeo)
                    lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"
                    db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado" or lote.modo == "solo_validar":
                        raise ValueError("El lote no admite confirmacion.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = previsualizar_inclusiones(
                        deserializar(lote.filas_json, []),
                        deserializar(lote.mapeo_json, {}),
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                    )
                    vista_actual = aplicar_modo_inclusiones(
                        vista_actual, lote.modo
                    )
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual)
                        db.session.commit()
                        return redirect(url_for(
                            "admin_comercial.importar_inclusiones_catalogo",
                            lote=lote.id,
                            error=(
                                "Los datos cambiaron desde la validacion. "
                                "Revisa la vista y confirma nuevamente."
                            ),
                        ))
                    aplicables = [
                        fila for fila in vista_actual
                        if fila["accion"] not in {"rechazado", "sin_cambios"}
                    ]
                    if not aplicables:
                        raise ValueError("El lote no contiene filas aplicables.")
                    conteos = aplicar_inclusiones(
                        vista_actual,
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                        db_session=db.session,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items():
                        setattr(lote, campo, valor)
                    lote.estado = "confirmado"
                    lote.fecha_confirmacion = ahora_utc_naive()
                    db.session.commit()
                    dependencias["registrar_auditoria"](
                        "Confirmó importación de productos por catálogo",
                        entidad="importacion_masiva_costo",
                        entidad_id=lote.id,
                        detalle=(
                            f"Unidad {unidad_activa.id}; "
                            f"{conteos['creados']} creados; "
                            f"{conteos['actualizados']} actualizados; "
                            f"{conteos['rechazados']} rechazados."
                        ),
                    )
                return redirect(url_for(
                    "admin_comercial.importar_inclusiones_catalogo", lote=lote.id,
                ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_comercial.importar_inclusiones_catalogo",
                error=str(error),
            ))

        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(
            id=lote_id,
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            tipo_datos=tipo_lote,
        ).first() if lote_id else None
        return render_template(
            "admin_importacion_inclusiones_catalogo.html",
            organizacion=organizacion,
            unidad_activa=unidad_activa,
            lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=deserializar(lote.vista_previa_json, []) if lote else [],
            campos=CAMPOS_INCLUSIONES,
            historial=Lote.query.filter_by(
                organizacion_id=organizacion.id,
                unidad_negocio_id=unidad_activa.id,
                tipo_datos=tipo_lote,
            ).order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route(
        "/admin/comercial/importaciones/inclusiones-catalogo/plantilla"
    )
    @dependencias["login_required"]
    def plantilla_importacion_inclusiones_catalogo():
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        return send_file(
            plantilla_inclusiones_catalogo(),
            as_attachment=True,
            download_name="plantilla_productos_por_catalogo.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    @blueprint.route(
        "/admin/comercial/importaciones/logistica-catalogo",
        methods=["GET", "POST"],
    )
    @dependencias["login_required"]
    def importar_logistica_catalogo():
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        Lote = modelos["ImportacionMasivaCosto"]
        tipo_lote = "logistica_catalogo"
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
                        tipo_datos=tipo_lote,
                        nombre_archivo=archivo.filename,
                        nombre_hoja=lectura["hoja"],
                        estado="cargado",
                        modo="actualizar",
                        encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(
                            sugerir_mapeo_logistica(lectura["encabezados"])
                        ),
                        total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote)
                    db.session.commit()
                    return redirect(url_for(
                        "admin_comercial.importar_logistica_catalogo",
                        lote=lote.id,
                    ))
                lote = Lote.query.filter_by(
                    id=int(request.form.get("lote_id")),
                    organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad_activa.id,
                    tipo_datos=tipo_lote,
                ).first()
                if lote is None:
                    raise ValueError("El lote no existe en la unidad activa.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {
                        str(i): (
                            (request.form.get(f"col_{i}") or "").strip()
                            if request.form.get(f"usar_{i}") == "1" else ""
                        )
                        for i in range(len(encabezados))
                    }
                    vista = previsualizar_logistica(
                        deserializar(lote.filas_json, []), mapeo,
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                    )
                    lote.mapeo_json = serializar(mapeo)
                    lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"
                    db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado":
                        raise ValueError("Primero validá el mapeo.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = previsualizar_logistica(
                        deserializar(lote.filas_json, []),
                        deserializar(lote.mapeo_json, {}),
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                    )
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual)
                        db.session.commit()
                        return redirect(url_for(
                            "admin_comercial.importar_logistica_catalogo",
                            lote=lote.id,
                            error=(
                                "Los datos cambiaron desde la validacion. "
                                "Revisa la vista y confirma nuevamente."
                            ),
                        ))
                    if not any(f["accion"] == "actualizar" for f in vista_actual):
                        raise ValueError("El lote no contiene filas aplicables.")
                    conteos = aplicar_logistica(
                        vista_actual,
                        organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id,
                        modelos=modelos,
                        db_session=db.session,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items():
                        setattr(lote, campo, valor)
                    lote.estado = "confirmado"
                    lote.fecha_confirmacion = ahora_utc_naive()
                    db.session.commit()
                    dependencias["registrar_auditoria"](
                        "Confirmó importación de ficha física por catálogo",
                        entidad="importacion_masiva_costo",
                        entidad_id=lote.id,
                        detalle=(
                            f"Unidad {unidad_activa.id}; "
                            f"{conteos['actualizados']} actualizados; "
                            f"{conteos['rechazados']} rechazados."
                        ),
                    )
                return redirect(url_for(
                    "admin_comercial.importar_logistica_catalogo", lote=lote.id,
                ))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for(
                "admin_comercial.importar_logistica_catalogo", error=str(error),
            ))

        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(
            id=lote_id,
            organizacion_id=organizacion.id,
            unidad_negocio_id=unidad_activa.id,
            tipo_datos=tipo_lote,
        ).first() if lote_id else None
        return render_template(
            "admin_importacion_logistica_catalogo.html",
            organizacion=organizacion,
            unidad_activa=unidad_activa,
            lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=deserializar(lote.vista_previa_json, []) if lote else [],
            campos=CAMPOS_LOGISTICA,
            historial=Lote.query.filter_by(
                organizacion_id=organizacion.id,
                unidad_negocio_id=unidad_activa.id,
                tipo_datos=tipo_lote,
            ).order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route(
        "/admin/comercial/importaciones/logistica-catalogo/plantilla"
    )
    @dependencias["login_required"]
    def plantilla_importacion_logistica_catalogo():
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        return send_file(
            plantilla_logistica_catalogo(),
            as_attachment=True,
            download_name="plantilla_ficha_fisica_por_catalogo.xlsx",
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    @blueprint.route("/admin/comercial/importaciones/datos-canal/<tipo>", methods=["GET", "POST"])
    @dependencias["login_required"]
    def importar_datos_comerciales_canal(tipo):
        usuario, organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        unidad_activa, _unidades = contexto_comercial(organizacion)
        campos = campos_datos_canal(tipo)
        Lote = modelos["ImportacionMasivaCosto"]
        tipo_lote = f"canal_{tipo}"
        try:
            if request.method == "POST":
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename: raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo, request.form.get("hoja"))
                    lote = Lote(
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id,
                        usuario_id=getattr(usuario, "id", None), tipo_datos=tipo_lote,
                        nombre_archivo=archivo.filename, nombre_hoja=lectura["hoja"],
                        estado="cargado", modo="crear_observaciones",
                        encabezados_json=serializar(lectura["encabezados"]),
                        filas_json=serializar(lectura["filas"]),
                        mapeo_json=serializar(sugerir_mapeo_datos_canal(lectura["encabezados"], tipo)),
                        total_filas=len(lectura["filas"]),
                    )
                    db.session.add(lote); db.session.commit()
                    return redirect(url_for("admin_comercial.importar_datos_comerciales_canal", tipo=tipo, lote=lote.id))
                lote = Lote.query.filter_by(
                    id=int(request.form.get("lote_id")), organizacion_id=organizacion.id,
                    unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote,
                ).first()
                if lote is None: raise ValueError("El lote no existe en la unidad activa.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {str(i): ((request.form.get(f"col_{i}") or "").strip() if request.form.get(f"usar_{i}") == "1" else "") for i in range(len(encabezados))}
                    vista = previsualizar_datos_canal(
                        deserializar(lote.filas_json, []), mapeo, tipo,
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, modelos=modelos,
                    )
                    lote.mapeo_json = serializar(mapeo); lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"; db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado": raise ValueError("Primero validá el mapeo.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = previsualizar_datos_canal(
                        deserializar(lote.filas_json, []), deserializar(lote.mapeo_json, {}), tipo,
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, modelos=modelos,
                    )
                    if serializar(vista_actual) != serializar(vista_guardada):
                        lote.vista_previa_json = serializar(vista_actual); db.session.commit()
                        return redirect(url_for("admin_comercial.importar_datos_comerciales_canal", tipo=tipo, lote=lote.id, error="Los datos internos cambiaron. Revisá la vista y confirmá nuevamente."))
                    if not any(fila["accion"] == "crear_observacion" for fila in vista_actual): raise ValueError("El lote no contiene filas aplicables.")
                    conteos = aplicar_datos_canal(
                        vista_actual, tipo, organizacion_id=organizacion.id,
                        unidad_negocio_id=unidad_activa.id, lote_id=lote.id, usuario=usuario,
                        modelos=modelos, db_session=db.session,
                    )
                    lote = db.session.get(Lote, lote.id)
                    for campo, valor in conteos.items(): setattr(lote, campo, valor)
                    lote.estado = "confirmado"; lote.fecha_confirmacion = ahora_utc_naive(); db.session.commit()
                    dependencias["registrar_auditoria"](
                        "Importó observaciones comerciales de canal", entidad="importacion_masiva_costo",
                        entidad_id=lote.id, detalle=f"Sección {tipo}; {conteos['creados']} creadas; {conteos['rechazados']} rechazadas.",
                    )
                return redirect(url_for("admin_comercial.importar_datos_comerciales_canal", tipo=tipo, lote=lote.id))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_comercial.importar_datos_comerciales_canal", tipo=tipo, error=str(error)))
        lote_id = request.args.get("lote", type=int)
        lote = Lote.query.filter_by(id=lote_id, organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).first() if lote_id else None
        return render_template(
            "admin_importacion_datos_canal.html", organizacion=organizacion,
            unidad_activa=unidad_activa, tipo=tipo, campos=campos, lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=deserializar(lote.vista_previa_json, []) if lote else [],
            historial=Lote.query.filter_by(organizacion_id=organizacion.id, unidad_negocio_id=unidad_activa.id, tipo_datos=tipo_lote).order_by(Lote.fecha_creacion.desc()).limit(20).all(),
            error=(request.args.get("error") or "").strip(),
        )

    @blueprint.route("/admin/comercial/importaciones/datos-canal/<tipo>/plantilla")
    @dependencias["login_required"]
    def plantilla_importacion_datos_comerciales_canal(tipo):
        _usuario, _organizacion, respuesta = acceso()
        if respuesta is not None: return respuesta
        campos_datos_canal(tipo)
        return send_file(
            plantilla_datos_canal(tipo), as_attachment=True,
            download_name=f"plantilla_canal_{tipo}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

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
        elif tipo == "maquinas":
            registros = obtener_fuentes_costo(
                organizacion.id, unidad.id, modelos=modelos,
            )["maquinas"]
            for r in registros:
                v = next((x for x in r.versiones_costo if x.vigente), None)
                filas.append([
                    r.codigo, r.nombre, r.categoria,
                    v.valor_adquisicion_centavos / 100 if v else "",
                    v.valor_residual_centavos / 100 if v else "",
                    v.vida_util_horas if v else "",
                    v.potencia_kw if v else "",
                    v.factor_carga_pct if v else "",
                    v.costo_kwh_centavos / 100 if v else "",
                    v.mantenimiento_mensual_centavos / 100 if v else "",
                    v.otros_costos_mensuales_centavos / 100 if v else "",
                    v.horas_productivas_mensuales if v else "",
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
                filas += [[p.producto.sku, "maquina", x.maquina.codigo, "", "", x.nombre, x.minutos, "", ""] for x in getattr(p, "maquinas_costeo", [])]
                filas += [[p.producto.sku, "costo_fijo", x.costo_fijo.codigo, "", "", "", "", x.porcentaje_asignacion, x.unidades_mensuales] for x in p.costos_fijos_costeo]
        salida = exportar_excel_tabla(config["titulo"], encabezados, filas) if formato == "xlsx" else exportar_pdf_tabla(config["titulo"], unidad.nombre, encabezados, filas) if formato == "pdf" else None
        if salida is None: raise ValueError("Formato no válido.")
        return send_file(salida, as_attachment=True, download_name=f"{tipo}.{formato}", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if formato == "xlsx" else "application/pdf")

    return blueprint
