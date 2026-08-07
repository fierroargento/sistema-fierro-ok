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
from services.fechas import ahora_utc_naive
from services.exportacion_perfiles_costeo import (
    exportar_excel_perfiles,
    exportar_pdf_perfiles,
    plantilla_excel_productos,
)
from services.tenant_context import TenantError, resolver_tenant_usuario


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

    @blueprint.route("/admin/comercial")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        return render_template(
            "admin_comercial.html", organizacion=organizacion,
            **obtener_datos_panel_comercial(organizacion.id, modelos=modelos),
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
            mensaje = procesar_accion_comercial(
                accion, request.form, organizacion=organizacion,
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
        return render_template(
            "admin_fuentes_costos.html",
            organizacion=organizacion,
            unidades=modelos["UnidadNegocio"].query.filter_by(
                organizacion_id=organizacion.id,
                activa=True,
            ).order_by(modelos["UnidadNegocio"].nombre).all(),
            **obtener_fuentes_costo(organizacion.id, modelos=modelos),
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
            mensaje = procesar_accion_fuente_costo(
                accion,
                request.form,
                organizacion=organizacion,
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
        ).first() if lote_id else None
        return render_template(
            "admin_importacion_productos_costeo.html",
            organizacion=organizacion, lote=lote,
            encabezados=deserializar(lote.encabezados_json, []) if lote else [],
            filas=deserializar(lote.filas_json, []) if lote else [],
            mapeo=deserializar(lote.mapeo_json, {}) if lote else {},
            vista=deserializar(lote.vista_previa_json, []) if lote else [],
            campos=CAMPOS_PRODUCTOS,
            historial=Lote.query.filter_by(
                organizacion_id=organizacion.id,
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
        perfiles = modelos["PerfilCosteoProducto"].query.filter_by(
            organizacion_id=organizacion.id
        ).order_by(modelos["PerfilCosteoProducto"].fecha_creacion).all()
        if formato == "xlsx":
            return send_file(
                exportar_excel_perfiles(perfiles), as_attachment=True,
                download_name="productos_clasificacion.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        if formato == "pdf":
            return send_file(
                exportar_pdf_perfiles(perfiles, organizacion.nombre),
                as_attachment=True, download_name="productos_clasificacion.pdf",
                mimetype="application/pdf",
            )
        raise ValueError("Formato de exportacion no valido.")

    return blueprint
