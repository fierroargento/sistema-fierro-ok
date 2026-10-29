"""Materiales de Compras sobre los maestros y precios productivos existentes."""
from sqlalchemy import or_
from services.fuentes_costo_productivo import crear_insumo, registrar_precio_insumo
from services.insumos_presentacion import leer, preparar_precio, guardar_precio


def consultar(org, unidad, modelos, session, buscar='', pagina=1, ver=None):
    I=modelos['InsumoProductivo'];V=modelos['InsumoPrecioVersion']
    q=session.query(I).filter_by(organizacion_id=org,unidad_negocio_id=unidad)
    if buscar:
        texto=buscar.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        q=q.filter(or_(I.codigo.ilike('%'+texto+'%',escape='\\'),I.nombre.ilike('%'+texto+'%',escape='\\')))
    total=q.count();pagina=min(max(1,pagina),max(1,(total+24)//25))
    insumos=q.order_by(I.nombre,I.id).offset((pagina-1)*25).limit(25).all()
    ids=[i.id for i in insumos]
    vigentes=session.query(V).filter(V.insumo_id.in_(ids),V.vigente.is_(True)).order_by(V.moneda).all() if ids else []
    precios={}
    for v in vigentes:precios.setdefault(v.insumo_id,[]).append(v)
    detalle=None;historial=[]
    if ver is not None:
        detalle=session.query(I).filter_by(id=ver,organizacion_id=org,unidad_negocio_id=unidad).first()
        if detalle is None:raise ValueError('El material no pertenece a la unidad activa.')
        historial=session.query(V).filter_by(insumo_id=detalle.id).order_by(V.vigente_desde.desc(),V.id.desc()).limit(20).all()
    presentaciones=leer(session,org,unidad)
    return dict(materiales=insumos,precios=precios,total=total,pagina=pagina,paginas=max(1,(total+24)//25),detalle=detalle,historial=historial,presentaciones={i.id:presentaciones.get(i.id,{}) for i in insumos})


def guardar(form, org, unidad, modelos, session, usuario_id):
    I=modelos['InsumoProductivo'];V=modelos['InsumoPrecioVersion']
    accion=form.get('accion')
    if accion=='crear':
        i=crear_insumo(organizacion_id=org.id,unidad_negocio_id=unidad.id,codigo=form.get('codigo'),nombre=form.get('nombre'),tipo=form.get('tipo'),unidad_medida=form.get('unidad_medida'),
            Organizacion=modelos['Organizacion'],UnidadNegocio=modelos['UnidadNegocio'],InsumoProductivo=I,db_session=session,commit=False)
        if not str(form.get('precio_unitario') or '').strip():return i
    elif accion=='precio':
        ident=str(form.get('insumo_id') or '')
        i=session.query(I).filter_by(id=int(ident),organizacion_id=org.id,unidad_negocio_id=unidad.id).with_for_update().first() if ident.isdecimal() else None
        if i is None:raise ValueError('El material no pertenece a la unidad activa.')
        if not i.activo:raise ValueError('El material está inactivo.')
    else:raise ValueError('La acción de materiales no es válida.')
    moneda=str(form.get('moneda') or '').upper()
    if moneda not in {'ARS','USD'}:raise ValueError('Elegí moneda ARS o USD.')
    actual=session.query(V).filter_by(insumo_id=i.id,moneda=moneda,vigente=True).first()
    if accion=='precio' and str(form.get('version_actual') or '')!=str(actual.id if actual else ''):raise ValueError('El precio cambió. Cerrá y recargá antes de guardar.')
    for campo,limite in [('proveedor_referencia',200),('comprobante_referencia',120),('observacion',500)]:
        if len(str(form.get(campo) or ''))>limite:raise ValueError('La referencia ingresada supera su longitud permitida.')
    # Conservar el bulto y las medidas originales: editar el precio unitario no borra la presentación.
    presentacion=leer(session,org.id,unidad.id).get(i.id,{})
    datos=dict(precio_unitario=form.get('precio_unitario'),base_precio='unitario',cantidad_bulto=presentacion.get('cantidad_bulto'),medidas_origen=presentacion.get('medidas_origen'))
    plan=preparar_precio(datos)
    v=registrar_precio_insumo(i,moneda=moneda,precio_unitario_centavos=plan['unitario_centavos'],proveedor_referencia=form.get('proveedor_referencia'),comprobante_referencia=form.get('comprobante_referencia'),observacion=form.get('observacion'),creado_por_usuario_id=usuario_id,InsumoPrecioVersion=V,db_session=session,commit=False)
    guardar_precio(v,i,datos,session,org.id)
    return i
