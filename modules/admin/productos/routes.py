"""Administración tenant del maestro único de productos."""
from io import BytesIO
from flask import abort, send_file, jsonify
from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for

from services.productos_consultas import obtener_panel_productos_plataforma
from services.productos_ficha_maestra import construir_filas, datos_de_formulario, guardar_ficha
from services.producto_habilitaciones import TIPOS, USOS
from services.importacion_maestro_productos import aplicar_lote, firmar_lote, leer_lote, plantilla_csv, previsualizar_lote
from services.tenant_context import TenantError, resolver_tenant_usuario
from services.productos_datos_generales import esquema_datos_disponible, leer_formulario_completo, guardar_datos_generales


def crear_blueprint_productos(*, dependencias):
    blueprint = Blueprint("admin_productos", __name__)
    db = dependencias["db"]
    login_required = dependencias["login_required"]
    usuario_actual = dependencias["usuario_actual"]
    registrar_auditoria = dependencias["registrar_auditoria"]
    UsuarioOrganizacion = dependencias["UsuarioOrganizacion"]
    Producto = dependencias["Producto"]

    def resolver_acceso():
        usuario = usuario_actual()
        try:
            membresia = resolver_tenant_usuario(usuario,
                UsuarioOrganizacion=UsuarioOrganizacion,
                organizacion_id=session.get("organizacion_id"))
        except TenantError as error:
            return None, None, redirect(url_for("inicio", error=str(error)))
        if membresia.rol != "admin":
            return None, None, redirect(url_for("inicio"))
        session["organizacion_id"] = membresia.organizacion_id
        return usuario, membresia.organizacion, None

    @blueprint.route("/admin/productos/<int:producto_id>/imagenes/<int:imagen_id>")
    @login_required
    def imagen(producto_id, imagen_id):
        _, organizacion, respuesta = resolver_acceso()
        if respuesta is not None: return respuesta
        if not esquema_datos_disponible(db.session): abort(404)
        from models.producto_datos_generales import ProductoImagenMaestra
        registro = db.session.query(ProductoImagenMaestra).join(Producto, Producto.id == ProductoImagenMaestra.producto_id).filter(
            ProductoImagenMaestra.id == imagen_id, ProductoImagenMaestra.producto_id == producto_id,
            ProductoImagenMaestra.organizacion_id == organizacion.id, Producto.organizacion_id == organizacion.id).first()
        if registro is None: abort(404)
        respuesta = send_file(BytesIO(registro.contenido), mimetype=registro.mime,
            download_name=registro.nombre, etag=registro.sha256, max_age=0)
        respuesta.headers['Cache-Control'] = 'private, no-cache'
        respuesta.headers['X-Content-Type-Options'] = 'nosniff'
        return respuesta

    @blueprint.route("/admin/productos/plantilla.csv")
    @login_required
    def plantilla():
        _, _, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        return Response(plantilla_csv(), content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="plantilla_maestro_productos.csv"'})

    @blueprint.route("/admin/productos/calcular-fabricacion", methods=["POST"])
    @login_required
    def calcular_fabricacion():
        _, organizacion, respuesta=resolver_acceso()
        if respuesta is not None:return respuesta
        if request.content_length and request.content_length>110000:return jsonify(error="La ficha supera el tamaño permitido."),400
        from services.productos_produccion_maestro import preparar, calcular
        try:
            if request.form.get('tipo')!='produccion':raise ValueError('El cálculo requiere un producto de producción.')
            ident=request.form.get('producto_id') or None
            if ident is not None:
                if not ident.isdigit():raise ValueError('El producto no es válido.')
                ident=int(ident)
            plan=preparar(request.form.get('produccion_json',''),db.session,organizacion.id,ident)
            resultado=calcular(plan,organizacion.id)
            return jsonify(resultado)
        except ValueError as error:
            return jsonify(error=str(error)),400

    @blueprint.route("/admin/productos", methods=["GET", "POST"])
    @login_required
    def panel():
        usuario, organizacion, respuesta = resolver_acceso()
        if respuesta is not None:
            return respuesta
        mensaje = (request.args.get("ok") or "").strip()
        error = (request.args.get("error") or "").strip()[:400]
        filtro_sku = (request.args.get("sku") or "").strip()
        vista, token, formulario_error = None, "", None
        if request.method == "POST":
            if request.content_length is not None and request.content_length > 12 * 1024 * 1024:
                return redirect(url_for("admin_productos.panel", error="No se guardó: el formulario supera 12 MB. Usá hasta 5 imágenes de 2 MB."))
            accion = request.form.get("accion", "")
            try:
                if accion in {"crear_producto", "editar_producto"}:
                    producto_id = int(request.form["producto_id"]) if accion == "editar_producto" else None
                    adicionales = leer_formulario_completo(request.form, request.files.getlist("imagenes_producto"))
                    plan_produccion=None
                    if request.form.get('tipo')=='produccion':
                        if request.form.get('produccion_presentada')=='1':
                            from services.productos_produccion_maestro import preparar as preparar_produccion
                            plan_produccion=preparar_produccion(request.form.get('produccion_json',''),db.session,organizacion.id,producto_id)
                        elif accion=='crear_producto':
                            raise ValueError('Completá la ficha de fabricación del nuevo producto de producción.')
                    producto = guardar_ficha(datos_de_formulario(request.form), Producto=Producto,
                        db_session=db.session, organizacion_id=(organizacion.id),
                        producto_id=producto_id, huella_esperada=request.form.get("huella", ""), commit=False)
                    guardar_datos_generales(producto, adicionales, db.session, usuario=usuario)
                    aviso_produccion=''
                    if plan_produccion is not None:
                        from services.productos_produccion_maestro import guardar as guardar_produccion
                        aviso_produccion=guardar_produccion(producto,plan_produccion,db.session,usuario,request.form.get('produccion_huella',''))
                    db.session.commit()
                    mensaje = f"{producto.sku}: ficha guardada correctamente." + (" " + aviso_produccion if aviso_produccion else "")
                    filtro_sku = producto.sku
                elif accion == "previsualizar_importacion":
                    archivo = request.files.get("archivo_productos")
                    if archivo is None or not archivo.filename:
                        raise ValueError("Seleccioná un archivo para previsualizar.")
                    vista = previsualizar_lote(leer_lote(archivo), Producto=Producto,
                        db_session=db.session, organizacion_id=organizacion.id)
                    token = firmar_lote(vista, organizacion.id, usuario.id, current_app.secret_key)
                elif accion == "confirmar_importacion":
                    conteo = aplicar_lote(request.form.get("lote_token", ""), Producto=Producto,
                        db_session=db.session, organizacion_id=organizacion.id,
                        usuario_id=usuario.id, secret_key=current_app.secret_key)
                    mensaje = f"Importación confirmada: {conteo['crear']} creados, {conteo['actualizar']} actualizados y {conteo['sin_cambios']} sin cambios."
                else:
                    raise ValueError("La acción no es válida. Usá Gestionar o Importar productos.")
                if vista is None:
                    try:
                        registrar_auditoria("Configuró maestro de productos", entidad="producto",
                            entidad_id=organizacion.id, detalle=f"Acción: {accion}. {mensaje}")
                    except Exception:
                        # El guardado ya terminó. No informar un rechazo falso
                        # ni inducir otra alta si falló únicamente su registro.
                        db.session.rollback()
                        current_app.logger.exception("La ficha se guardó pero falló su registro de auditoría")
                        mensaje += " El registro de auditoría quedó pendiente de revisión."
                    return redirect(url_for("admin_productos.panel", ok=mensaje, sku=filtro_sku, _anchor="productos-listado"))
            except Exception as error_accion:
                db.session.rollback()
                current_app.logger.warning("No se pudo guardar el maestro de productos: %s", type(error_accion).__name__)
                error = str(error_accion) if isinstance(error_accion, (ValueError, KeyError)) else "No se pudo guardar. No se aplicaron cambios; volvé a intentarlo."
                if accion in {"crear_producto", "editar_producto"}:
                    formulario_error = dict(request.form)
                    if accion == "editar_producto" and str(request.form.get("producto_id", "")).isdigit():
                        actual = db.session.query(Producto).filter_by(id=int(request.form["producto_id"]), organizacion_id=organizacion.id).first()
                        if actual is not None: filtro_sku = actual.sku
        datos = obtener_panel_productos_plataforma(Producto, organizacion_id=organizacion.id, filtro_sku=filtro_sku)
        preparado, filas = construir_filas(datos["productos"], db.session, organizacion.id)
        insumos = []
        if preparado:
            from models.fuentes_costo_productivo import InsumoProductivo
            insumos = db.session.query(InsumoProductivo).filter(
                InsumoProductivo.organizacion_id == organizacion.id,
                InsumoProductivo.tipo != "servicio_productivo",
            ).order_by(InsumoProductivo.codigo).all()
        componentes, unidades = [], []
        if preparado:
            from models.producto_ficha_maestra import ProductoFichaMaestra as Ficha
            from models.unidad_negocio import UnidadNegocio
            componentes = db.session.query(Producto, Ficha).join(Ficha, Ficha.producto_id == Producto.id).filter(
                Producto.organizacion_id == organizacion.id, Ficha.organizacion_id == organizacion.id,
                Ficha.activo.is_(True), Ficha.habilita_componente.is_(True),
                Ficha.tipo.in_(["simple", "produccion"]),
            ).order_by(Producto.sku).all()
            unidades = db.session.query(UnidadNegocio).filter_by(organizacion_id=organizacion.id).order_by(UnidadNegocio.nombre).all()
        completo = esquema_datos_disponible(db.session)
        proveedores, ubicaciones, clasificaciones = [], [], []
        if completo:
            from models.compras import ProveedorCompra
            from models.sucursal_operativa import SucursalOperativa
            from models.producto_datos_generales import ProductoDatosGenerales
            proveedores = db.session.query(ProveedorCompra).filter_by(organizacion_id=organizacion.id).order_by(ProveedorCompra.razon_social).all()
            ubicaciones = db.session.query(SucursalOperativa).filter_by(organizacion_id=organizacion.id).order_by(SucursalOperativa.nombre).all()
            clasificaciones = [dict(r._mapping) for r in db.session.query(ProductoDatosGenerales.rubro, ProductoDatosGenerales.subrubro, ProductoDatosGenerales.marca).filter_by(organizacion_id=organizacion.id).distinct().all()]
        from services.productos_produccion_maestro import disponible, modelos
        fabricacion_disponible=disponible(db.session)
        recursos_fabricacion={}
        if fabricacion_disponible:
            for grupo,(_,Recurso,_) in modelos()[1].items():
                recursos_fabricacion[grupo]=[{'id':r.id,'codigo':r.codigo,'nombre':r.nombre,
                    'unidad':getattr(r,'unidad_medida','minuto' if grupo in {'operaciones','maquinas'} else 'mes'),
                    'unidad_id':r.unidad_negocio_id,'activo':r.activo,'tipo_registro':getattr(r,'tipo_registro','')}
                    for r in db.session.query(Recurso).filter_by(organizacion_id=organizacion.id).order_by(Recurso.codigo)
                    if grupo!='fijos' or r.integra_costo_produccion]
        from services.productos_despiece import disponible as despiece_disponible
        return render_template("admin_productos.html", despiece_disponible=despiece_disponible(db.session), fabricacion_disponible=fabricacion_disponible, recursos_fabricacion=recursos_fabricacion, completo=completo, proveedores=proveedores, ubicaciones=ubicaciones, clasificaciones=clasificaciones, componentes=componentes, unidades_combo=unidades, mensaje=mensaje, error=error,
            organizacion=organizacion, preparado=preparado, filas=filas,
            tipos=TIPOS, usos=USOS, vista=vista, lote_token=token, insumos=insumos,
            formulario_error=formulario_error, **datos)

    return blueprint
