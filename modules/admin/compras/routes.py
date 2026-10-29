"""Panel tenant de compras preparatorias sin impacto automático."""

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session, url_for

from services.materias_primas_inventario import preparar_materia_prima, validar_existencia_insumo
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
    deserializar, leer_archivo, serializar,
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
    from services.proveedores_unidad import consulta as proveedores_consulta, exigir as exigir_proveedor, vincular, vincular_por_identidad, exigir_preparado
    from services.proveedores_unidad import previsualizar as previsualizar_unidad, para_importacion, operativo

    def contexto_formulario(unidad):
        if request.form.get('unidad_contexto_id', type=int) != unidad.id:
            raise ValueError('La unidad activa cambió. Volvé a abrir el formulario antes de guardar.')

    def vista_proveedores(filas, mapeo, organizacion, unidad):
        return previsualizar_unidad(filas, mapeo, Proveedor=modelos['ProveedorCompra'],
            organizacion_id=organizacion.id, unidad_id=unidad.id, session=db.session)


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
        if unidad is None and unidad_id is not None:
            return usuario, membresia.organizacion, None, redirect(url_for("inicio", error="Seleccioná una unidad activa válida para abrir Compras."))
        if unidad is None and unidades:
            unidad = unidades[0]
            session["unidad_negocio_id"] = unidad.id
        if unidad is None:
            return usuario, membresia.organizacion, None, redirect(url_for("admin_estructura.panel"))
        session["organizacion_id"] = membresia.organizacion_id
        return usuario, membresia.organizacion, unidad, None

    vistas_compras={'resumen','proveedores','ordenes','recepciones','facturas','mapeos','propuestas'}

    def vista_compras_actual(accion=None):
        vista=request.args.get('vista')
        if vista in vistas_compras:return vista
        if accion in {'vincular_proveedor','crear_proveedor','editar_proveedor'}:return 'proveedores'
        if accion in {'preparar_materia_prima','crear_mapeo_inventario'}:return 'mapeos'
        if accion in {'preparar_impactos','decidir_impacto'}:return 'propuestas'
        if accion=='registrar_factura':return 'facturas'
        if accion=='preparar_recepcion':return 'recepciones'
        return 'ordenes' if accion else 'resumen'

    @blueprint.route('/admin/compras/listas-proveedores/plantilla')
    @dependencias['login_required']
    def plantilla_lista_proveedor():
        _,_,_,respuesta=acceso()
        if respuesta is not None:return respuesta
        from services.listas_proveedores_compra import plantilla
        return send_file(plantilla(),as_attachment=True,download_name='Lista_proveedor_Fierro.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @blueprint.route('/admin/compras/listas-proveedores',methods=['GET','POST'])
    @dependencias['login_required']
    def listas_proveedores():
        from flask import current_app,abort
        from sqlalchemy.exc import IntegrityError
        from decimal import Decimal
        from services import listas_proveedores_compra as listas
        from models.listas_proveedores_compra import MaterialProveedorCompra as L,CotizacionProveedorCompra as C
        from models.fuentes_costo_productivo import InsumoPrecioVersion as V
        from scripts.preparar_listas_proveedores import preparado
        from services.proveedores_unidad import estados
        usuario,org,unidad,respuesta=acceso()
        if respuesta is not None:return respuesta
        proveedores=proveedores_consulta(modelos['ProveedorCompra'],org.id,unidad.id,db.session).order_by(modelos['ProveedorCompra'].razon_social).all()
        ident=request.form.get('proveedor_id') if request.method=='POST' else request.args.get('proveedor_id')
        p=next((p for p in proveedores if str(p.id)==str(ident)),None)
        if ident and p is None:abort(404)
        listo=preparado(db.session.connection());error='';status=200;vista=None;token=''
        campos=request.form.getlist('campos_actualizar') if request.method=='POST' else list(listas.CAMPOS)
        if request.method=='POST':
            try:
                contexto_formulario(unidad)
                listas.listo(db.session)
                listas.proveedor_valido(p,org.id,unidad.id,db.session)
                accion=request.form.get('accion')
                if accion=='vincular_material':
                    i=listas._material(request.form.get('insumo_id'),org.id,unidad.id,db.session)
                    listas.vincular(i,p,request.form.get('codigo_proveedor'),org.id,unidad.id,db.session)
                    mensaje='Material vinculado sin duplicar su ficha.'
                elif accion=='editar_codigo':
                    l=db.session.query(L).filter_by(id=request.form.get('vinculo_id',type=int),organizacion_id=org.id,unidad_negocio_id=unidad.id,proveedor_id=p.id).with_for_update().first()
                    if l is None or l.codigo!=request.form.get('codigo_anterior'):raise ValueError('El vínculo cambió. Recargá antes de editar.')
                    codigo=str(request.form.get('codigo_proveedor') or '').strip()
                    if not codigo or len(codigo)>120:raise ValueError('Completá el código del proveedor (máximo 120 caracteres).')
                    l.codigo=codigo;l.codigo_clave=codigo.upper();mensaje='Código actualizado. Se conserva el historial del material.'
                elif accion in {'revisar_lista','revisar_manual','revisar_codimat','revisar_vinculos_codimat'}:
                    if accion=='revisar_vinculos_codimat':
                        from services import listas_codimat as codimat
                        vista=codimat.leer_borrador(request.form.get('token_vinculacion',''),p.id,org.id,unidad.id,usuario.id,current_app.secret_key)
                        selecciones=[request.form.get('material_'+str(n),'') for n in range(len(vista.get('pendientes',[])))]
                        vista=codimat.resolver_vinculos(vista,selecciones,p,org.id,unidad.id,db.session)
                        campos=list(listas.CAMPOS)
                    elif accion=='revisar_codimat':
                        from services import listas_codimat as codimat
                        archivo=request.files.get('archivo_lista')
                        if archivo is None or not archivo.filename:raise ValueError('Seleccioná el XLSX original de Codimat.')
                        reglas=codimat.reglas(request.form.getlist('codimat_codigo'),request.form.getlist('codimat_descuento'),request.form.getlist('codimat_cantidad'))
                        vista=codimat.revisar(archivo,reglas,p,org.id,unidad.id,db.session)
                        campos=list(listas.CAMPOS)
                    elif accion=='revisar_lista':
                        archivo=request.files.get('archivo_lista')
                        if archivo is None or not archivo.filename:raise ValueError('Seleccioná la planilla XLSX o CSV.')
                        filas,campos=listas.lector.leer(archivo,campos)
                    else:
                        campos=list(listas.CAMPOS)
                        l=db.session.query(L).filter_by(id=request.form.get('vinculo_id',type=int),organizacion_id=org.id,unidad_negocio_id=unidad.id,proveedor_id=p.id).first()
                        if l is None:raise ValueError('El vínculo no pertenece al proveedor de esta unidad.')
                        filas=[dict(numero=1,valores={c:request.form.get(c,'') for c in campos}|{'codigo_proveedor':l.codigo},formulas=[])]
                    if accion not in {'revisar_codimat','revisar_vinculos_codimat'}:vista=listas.revisar(filas,campos,p,org.id,unidad.id,db.session)
                    if accion!='revisar_vinculos_codimat':vista['referencia']=(str(archivo.filename)[:120] if accion in {'revisar_lista','revisar_codimat'} else 'Cotización manual')
                    if vista['filas'] and not vista.get('pendientes') and not any(f['errores'] for f in vista['filas']) and (any(f['cambia'] for f in vista['filas']) or 'codimat' in vista):
                        token=listas.firmar(vista,p.id,org.id,unidad.id,usuario.id,current_app.secret_key)
                    mensaje=None
                elif accion=='confirmar_lista':
                    n=listas.confirmar(request.form.get('token_lista',''),p,org.id,unidad.id,usuario.id,current_app.secret_key,db.session)
                    mensaje=f'{n} cotizaciones actualizadas. El costo del material se conserva hasta elegir Usar en costo.'
                elif accion=='usar_costo':
                    listas.usar_en_costo(request.form.get('cotizacion_id',type=int),p,org.id,unidad.id,request.form.get('version_fuente'),db.session,getattr(usuario,'id',None))
                    mensaje='Cotización aplicada a la fuente de costo. Sin stock, pagos ni publicación de precios de venta.'
                else:raise ValueError('La acción no es válida.')
                if mensaje is not None:
                    db.session.commit()
                    dependencias['registrar_auditoria']('Compras: lista de proveedor',entidad='proveedor',entidad_id=p.id,detalle='Unidad '+str(unidad.id)+'. Acción '+accion+'. Sin movimientos operativos.')
                    return redirect(url_for('admin_compras.listas_proveedores',proveedor_id=p.id,ok=mensaje,pagina=request.args.get('pagina',1)))
            except (ValueError,IntegrityError) as exc:
                db.session.rollback();error=str(exc) if isinstance(exc,ValueError) else 'El código o la cotización cambió o está duplicado. Revisá y volvé a intentar.';status=400
        links=[];total=0;paginas=1;pagina=max(1,request.args.get('pagina',default=1,type=int) or 1);cotizaciones={};fuentes={};historia=[];detalle=None
        insumos=listas.materiales(org.id,unidad.id,db.session) if p else []
        if p and listo:
            q=db.session.query(L).filter_by(organizacion_id=org.id,unidad_negocio_id=unidad.id,proveedor_id=p.id)
            total=q.count();paginas=max(1,(total+24)//25);pagina=min(pagina,paginas)
            links=q.order_by(L.codigo,L.id).offset((pagina-1)*25).limit(25).all()
            ids=[l.id for l in links]
            for c in db.session.query(C).filter(C.vinculo_id.in_(ids),C.vigente.is_(True)).order_by(C.moneda):cotizaciones.setdefault(c.vinculo_id,[]).append(c)
            for v in db.session.query(V).filter(V.insumo_id.in_([l.insumo_id for l in links]),V.vigente.is_(True)):fuentes[(v.insumo_id,v.moneda)]=v
            ver=request.args.get('ver',type=int)
            if ver:
                detalle=q.filter_by(id=ver).first()
                if detalle is None:abort(404)
                historia=db.session.query(C).filter_by(vinculo_id=detalle.id).order_by(C.fecha.desc(),C.id.desc()).limit(20).all()
        from services.listas_codimat import reglas_actuales,firmar_borrador
        from models.listas_proveedores_compra import CalculoCotizacionProveedor
        reglas_codimat=reglas_actuales(org.id,unidad.id,p.id,db.session) if p and listo else []
        if vista and 'codimat' in vista:reglas_codimat=vista['codimat']['reglas']
        if error and request.form.get('accion')=='revisar_codimat':
            reglas_codimat=[dict(codigo=c,descuento=d,cantidad=q) for c,d,q in zip(request.form.getlist('codimat_codigo'),request.form.getlist('codimat_descuento'),request.form.getlist('codimat_cantidad'))][:500]
        calculos={d.cotizacion_id:d.datos for d in db.session.query(CalculoCotizacionProveedor).filter(CalculoCotizacionProveedor.cotizacion_id.in_([c.id for c in historia]))} if listo and historia else {}
        materiales_vinculables=insumos
        if vista and vista.get('pendientes'):
            catalogo_actual,_=listas.catalogo(org.id,unidad.id,p.id,db.session)
            ocupados={r['insumo_id'] for r in catalogo_actual.values()}|{l.insumo_id for l in listas.vinculos(org.id,unidad.id,p.id,db.session)}
            materiales_vinculables=[i for i in insumos if i.id not in ocupados]
        token_vinculacion=firmar_borrador(vista,p.id,org.id,unidad.id,usuario.id,current_app.secret_key) if vista and vista.get('pendientes') else ''
        return render_template('admin_compras_listas.html',token_vinculacion=token_vinculacion,materiales_vinculables=materiales_vinculables,reglas_codimat=reglas_codimat,calculos=calculos,organizacion=org,unidad_activa=unidad,proveedores=proveedores,proveedor=p,proveedor_habilitado=bool(p and estados(org.id,unidad.id,db.session).get(p.id)=='activo'),listo=listo,materiales=insumos,materiales_por_id={i.id:i for i in db.session.query(listas.I).filter_by(organizacion_id=org.id,unidad_negocio_id=unidad.id).filter(listas.I.id.in_([l.insumo_id for l in links]))},vinculos=links,cotizaciones=cotizaciones,fuentes=fuentes,total=total,pagina=pagina,paginas=paginas,detalle=detalle,historia=historia,vista=vista,token_lista=token,campos=campos,campos_disponibles=listas.CAMPOS,etiqueta=listas.lector.etiqueta,error=error,ok_feedback=request.args.get('ok',''),formulario_error={k:v for k,v in request.form.items() if k not in {'_csrf_token','unidad_contexto_id','token_lista'}} if error else None,dinero=lambda n:format(Decimal(n)/100,',.2f').replace(',','_').replace('.',',').replace('_','.')),status

    @blueprint.route('/admin/compras/materiales',methods=['GET','POST'])
    @dependencias['login_required']
    def materiales():
        from sqlalchemy.exc import IntegrityError
        from decimal import Decimal
        from services.compras_materiales import consultar, guardar as guardar_material
        usuario,organizacion,unidad,respuesta=acceso()
        if respuesta is not None:return respuesta
        error='';status=200
        if request.method=='POST':
            try:
                contexto_formulario(unidad)
                i=guardar_material(request.form,organizacion,unidad,modelos,db.session,getattr(usuario,'id',None))
                db.session.commit()
                dependencias['registrar_auditoria']('Compras: guardó material o precio',entidad='insumo',entidad_id=i.id,detalle='Fuente de costo; sin movimientos de stock ni publicación de precios.')
                return redirect(url_for('admin_compras.materiales',ok='Material guardado. Se conserva el historial de precios.'))
            except (ValueError,IntegrityError) as exc:
                db.session.rollback();error=str(exc) if isinstance(exc,ValueError) else 'El código ya existe o el precio cambió. Recargá antes de guardar.';status=400
        try:pagina=max(1,int(request.args.get('pagina','1')))
        except ValueError:pagina=1
        ver=request.args.get('ver',type=int)
        buscar=(request.args.get('buscar') or '').strip()[:120]
        try:datos=consultar(organizacion.id,unidad.id,modelos,db.session,buscar,pagina,ver)
        except ValueError:
            from flask import abort
            abort(404)
        return render_template('admin_compras_materiales.html',organizacion=organizacion,unidad_activa=unidad,buscar=buscar,error=error,ok_feedback=request.args.get('ok',''),formulario_error={k:v for k,v in request.form.items() if k not in {'_csrf_token','unidad_contexto_id'}} if error else None,dinero=lambda n:format(Decimal(n)/100,',.2f').replace(',','_').replace('.',',').replace('_','.'),**datos),status

    @blueprint.route('/admin/compras/buscar-proveedores')
    @dependencias['login_required']
    def buscar_proveedores():
        _,organizacion,unidad,respuesta=acceso()
        if respuesta is not None:return respuesta
        if request.args.get('unidad_contexto_id',type=int)!=unidad.id:
            return jsonify(error='La unidad activa cambió. Recargá antes de buscar.'),409
        from services.proveedores_unidad import buscar_para_vincular
        filas=buscar_para_vincular(request.args.get('q'),modelos['ProveedorCompra'],organizacion.id,db.session)
        salida=jsonify(proveedores=[dict(id=p.id,nombre=p.razon_social,codigo=p.codigo,cuit=p.cuit or '') for p in filas])
        salida.headers['Cache-Control']='no-store, private'
        return salida

    @blueprint.route("/admin/compras/consultar-cuit", methods=["POST"])
    @dependencias["login_required"]
    def consultar_cuit():
        _usuario, organizacion, _unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        from services.consulta_padron_web import responder_consulta_padron
        return responder_consulta_padron(organizacion.id)

    @blueprint.route("/admin/compras")
    @dependencias["login_required"]
    def panel():
        _usuario, organizacion, unidad, respuesta = acceso()
        if respuesta is not None:
            return respuesta
        datos = obtener_panel_compras(organizacion.id, unidad.id, modelos=modelos)
        from services.maestros_contacto import consultar_contactos, contactos_preparados
        datos['contactos_proveedores'] = {k:v for k,v in consultar_contactos(db.session, organizacion.id).items() if k in {p.id for p in datos['proveedores']}}
        datos['contactos_preparados'] = contactos_preparados(db.session)
        return render_template(
            "admin_compras.html", organizacion=organizacion, unidad_activa=unidad,vista_compras=vista_compras_actual(),
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
        exigir_listo = lambda: exigir_preparado(db.session)
        try:
            if request.method == "POST":
                contexto_formulario(unidad)
                exigir_listo()
                accion = (request.form.get("accion") or "").strip()
                if accion == "subir":
                    archivo = request.files.get("archivo")
                    if archivo is None or not archivo.filename:
                        raise ValueError("Seleccioná un archivo.")
                    lectura = leer_archivo(archivo, request.form.get("hoja"))
                    lote = Lote(
                        organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
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
                    unidad_negocio_id=unidad.id, tipo_datos=tipo_lote,
                ).first()
                if lote is None:
                    raise ValueError("El lote no pertenece a la unidad activa.")
                if accion == "mapear":
                    encabezados = deserializar(lote.encabezados_json, [])
                    mapeo = {
                        str(i): (
                            (request.form.get(f"col_{i}") or "").strip()
                            if request.form.get(f"usar_{i}") == "1" else ""
                        ) for i in range(len(encabezados))
                    }
                    vista = vista_proveedores(deserializar(lote.filas_json, []), mapeo, organizacion, unidad)
                    lote.mapeo_json = serializar(mapeo)
                    lote.vista_previa_json = serializar(vista)
                    lote.estado = "mapeado"
                    db.session.commit()
                elif accion == "confirmar":
                    if lote.estado != "mapeado":
                        raise ValueError("Primero validá el mapeo.")
                    vista_guardada = deserializar(lote.vista_previa_json, [])
                    vista_actual = vista_proveedores(deserializar(lote.filas_json, []), deserializar(lote.mapeo_json, {}), organizacion, unidad)
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
                        db_session=db.session, commit=False, unidad_negocio_id=unidad.id,
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
            unidad_negocio_id=unidad.id, tipo_datos=tipo_lote,
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
                organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
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
            contexto_formulario(unidad)
            exigir_preparado(db.session)
            if accion == "vincular_proveedor":
                elegido=request.form.get('proveedor_a_vincular')
                if elegido:
                    proveedor=modelos['ProveedorCompra'].query.filter_by(id=int(elegido),organizacion_id=organizacion.id).first() if elegido.isdecimal() else None
                    if proveedor is None:raise ValueError('Elegí un proveedor de la empresa en los resultados.')
                    vincular(proveedor,organizacion.id,unidad.id,db.session)
                else:
                    proveedor=vincular_por_identidad(request.form.get('identidad_proveedor'), modelos['ProveedorCompra'], organizacion.id, unidad.id, db.session)
                db.session.commit()
                mensaje=f"Proveedor {proveedor.codigo} vinculado a {unidad.nombre}."
            elif accion == "crear_proveedor":
                creado = crear_proveedor(
                    request.form, organizacion_id=organizacion.id,
                    ProveedorCompra=modelos["ProveedorCompra"], db_session=db.session, commit=False,
                )
                estado_unidad=creado.estado
                creado.estado="activo"
                vincular(creado, organizacion.id, unidad.id, db.session, estado=estado_unidad)
                db.session.commit()
                mensaje = f"Proveedor {creado.codigo} creado en {unidad.nombre}."
            elif accion == "editar_proveedor":
                proveedor = modelos["ProveedorCompra"].query.filter_by(id=int(request.form.get("proveedor_id")), organizacion_id=organizacion.id).first()
                exigir_proveedor(proveedor, organizacion.id, unidad.id, db.session)
                campos = list(CAMPOS_PROVEEDORES)
                datos_proveedor = dict(request.form)
                datos_proveedor["codigo"] = proveedor.codigo
                proveedores = proveedores_consulta(modelos["ProveedorCompra"], organizacion.id, unidad.id, db.session).all()
                vista = previsualizar_proveedores([{"numero": 1, "valores": [datos_proveedor.get(campo, "") for campo in campos]}], {str(i): campo for i, campo in enumerate(campos)}, proveedores=para_importacion(proveedores, organizacion.id, unidad.id, db.session))
                if vista[0]["errores"]: raise ValueError("; ".join(vista[0]["errores"]))
                if vista[0]["proveedor_id"] != proveedor.id: raise ValueError("La identidad del proveedor cambió.")
                aplicar_proveedores(vista, organizacion_id=organizacion.id, ProveedorCompra=modelos["ProveedorCompra"], db_session=db.session, commit=False, unidad_negocio_id=unidad.id)
                if "telefono_contacto" in request.form:
                    from services.maestros_contacto import guardar_contacto
                    guardar_contacto(db.session, proveedor, request.form.get("telefono_contacto"))
                db.session.commit()
                mensaje = f"Proveedor {proveedor.codigo} actualizado."
            elif accion == "crear_orden":
                proveedor = modelos["ProveedorCompra"].query.filter_by(
                    id=int(request.form.get("proveedor_id")), organizacion_id=organizacion.id,
                ).first()
                exigir_proveedor(proveedor, organizacion.id, unidad.id, db.session)
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
                    unidad_negocio_id=unidad.id, proveedor=operativo(proveedor, organizacion.id, unidad.id, db.session), insumo=insumo,
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
            elif accion == "preparar_materia_prima":
                insumo = modelos["InsumoProductivo"].query.filter_by(
                    id=int(request.form.get("insumo_id")), organizacion_id=organizacion.id,
                ).first()
                item, creado = preparar_materia_prima(
                    insumo=insumo, sku=request.form.get("sku"),
                    organizacion_id=organizacion.id, unidad_negocio_id=unidad.id,
                    Producto=modelos["Producto"], ItemInventario=modelos["ItemInventario"],
                    db_session=db.session, precision_inventario=request.form.get("precision_inventario", "unidad"),
                )
                mensaje = (f"SKU {item.sku} preparado desactivado, sin existencias ni stock."
                           if creado else f"El insumo ya está preparado como {item.sku}; no se duplicó.")
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
                validar_existencia_insumo(insumo, existencia, organizacion.id, unidad.id)
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
            return redirect(url_for("admin_compras.panel", ok=mensaje, vista=vista_compras_actual(accion)))
        except Exception as error:
            db.session.rollback()
            return redirect(url_for("admin_compras.panel", error=str(error), vista=vista_compras_actual(request.form.get("accion"))))

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

