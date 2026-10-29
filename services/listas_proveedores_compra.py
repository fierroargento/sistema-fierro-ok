"""Cotizaciones independientes, revisión firmada y aplicación explícita al costo."""
import json
from collections import defaultdict
from decimal import Decimal,InvalidOperation
from hashlib import sha256
from io import BytesIO
from sqlalchemy import inspect
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired
from models.listas_proveedores_compra import MaterialProveedorCompra as L,CotizacionProveedorCompra as C
from models.fuentes_costo_productivo import InsumoProductivo as I,InsumoPrecioVersion as V
from services.proveedores_unidad import exigir,operativo
from services.insumos_presentacion import preparar_precio
from services.catalogos_comerciales import importe_a_centavos
from scripts.preparar_listas_proveedores import preparado
from services import actualizacion_selectiva_productos as lector
CAMPOS=lector.PRECIOS
SALT='compras-listas-proveedor-unidad-v1'

def listo(session):
    if not preparado(session.connection()):raise ValueError('Falta preparar las listas de proveedores en staging.')

def proveedor_valido(p,org,unidad,session):
    exigir(p,org,unidad,session)
    if operativo(p,org,unidad,session).estado!='activo':raise ValueError('Activá el proveedor en esta unidad antes de cargar su lista.')

def materiales(org,unidad,session):
    return session.query(I).filter_by(organizacion_id=org,unidad_negocio_id=unidad,activo=True).order_by(I.nombre).all()

def _material(ident,org,unidad,session):
    s=str(ident or '')
    i=session.query(I).filter_by(id=int(s),organizacion_id=org,unidad_negocio_id=unidad,activo=True).first() if s.isdecimal() else None
    if i is None:raise ValueError('El material no pertenece a la unidad activa o está inactivo.')
    return i

def vincular(i,p,codigo,org,unidad,session):
    listo(session);proveedor_valido(p,org,unidad,session);_material(i.id,org,unidad,session)
    codigo=str(codigo or '').strip()
    if not codigo or len(codigo)>120:raise ValueError('Completá el código del proveedor (máximo 120 caracteres).')
    filas=session.query(L).filter_by(organizacion_id=org,unidad_negocio_id=unidad,proveedor_id=p.id).with_for_update().all()
    for l in filas:
        if l.codigo_clave==codigo.upper() or l.insumo_id==i.id:
            if l.codigo_clave==codigo.upper() and l.insumo_id==i.id:return l
            raise ValueError('Ese código o material ya tiene otro vínculo con el proveedor. No se reemplazó.')
    l=L(organizacion_id=org,unidad_negocio_id=unidad,proveedor_id=p.id,insumo_id=i.id,codigo=codigo,codigo_clave=codigo.upper());session.add(l);session.flush();return l

def vinculos(org,unidad,p,session):
    return session.query(L).filter_by(organizacion_id=org,unidad_negocio_id=unidad,proveedor_id=p).order_by(L.codigo).all()

def _legados(org,unidad,proveedor,session):
    """Reutiliza códigos ya vinculados a productos con fuente explícita de esta unidad."""
    from models.producto_datos_generales import ProductoProveedor as PP
    from models.producto_ficha_maestra import ProductoFichaMaestra as F
    from models.producto import Producto as P
    i=inspect(session.connection())
    if not all(i.has_table(m.__tablename__) for m in [PP,F,P]):return []
    # No atribuir productos generales a una unidad por descarte.
    return session.query(PP.codigo,P.sku,F.insumo_id).join(P,P.id==PP.producto_id).join(F,F.producto_id==PP.producto_id).join(I,I.id==F.insumo_id).filter(PP.organizacion_id==org,PP.proveedor_id==proveedor,P.organizacion_id==org,F.organizacion_id==org,I.organizacion_id==org,I.unidad_negocio_id==unidad,I.activo.is_(True)).all()

def catalogo(org,unidad,p,session):
    propios={i.id:i for i in materiales(org,unidad,session)}
    salida={l.codigo_clave:dict(insumo_id=l.insumo_id,codigo=l.codigo,vinculo_id=l.id,skus=[]) for l in vinculos(org,unidad,p,session) if l.insumo_id in propios}
    explicitos={r['insumo_id'] for r in salida.values()}
    for codigo,sku,insumo in _legados(org,unidad,p,session):
        codigo=str(codigo or '').strip()
        if not codigo:continue
        clave=codigo.upper()
        if insumo in explicitos and clave not in salida:continue
        if clave in salida and salida[clave]['insumo_id']!=insumo:raise ValueError('Hay códigos de proveedor ambiguos; revisá sus vínculos antes de importar.')
        if clave not in salida:salida[clave]=dict(insumo_id=insumo,codigo=codigo,vinculo_id=None,skus=[])
        if sku and sku.casefold() not in salida[clave]['skus']:salida[clave]['skus'].append(sku.casefold())
    return salida,propios

def _firma(datos):return sha256(json.dumps(datos,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def _actual(l,moneda,session):
    return session.query(C).filter_by(vinculo_id=l,moneda=moneda,vigente=True).first() if l else None

def _datos(c):
    return dict(precio_proveedor=str(Decimal(c.precio_bulto_centavos if c.base_precio=='bulto' else c.precio_unitario_centavos)/100),base_precio=c.base_precio,cantidad_bulto=str(c.cantidad_bulto) if c.cantidad_bulto is not None else '',moneda_proveedor=c.moneda,medidas_origen=c.medidas_origen) if c else {}

def _plan(valores,previo):
    datos=_datos(previo);datos.update({k:v for k,v in valores.items() if k in CAMPOS and str(v).strip()})
    if 'precio_proveedor' not in datos:raise ValueError('Falta el precio del proveedor.')
    moneda=str(datos.get('moneda_proveedor') or 'ARS').upper()
    if moneda not in {'ARS','USD'}:raise ValueError('Moneda proveedor: elegí ARS o USD.')
    base=str(datos.get('base_precio') or '').lower()
    if base not in {'unitario','bulto'}:raise ValueError('Completá Cotización proveedor: unitario o bulto.')
    # Si cambió la base, hace falta un importe explícito; nunca reinterpretar el anterior.
    if previo and base!=previo.base_precio and not str(valores.get('precio_proveedor') or '').strip():raise ValueError('Para cambiar la base de cotización también cargá el precio.')
    try:datos['precio_proveedor']=str(Decimal(importe_a_centavos(datos['precio_proveedor']))/100)
    except (InvalidOperation,ValueError,OverflowError):raise ValueError('Precio proveedor inválido. Usá, por ejemplo, 1234,56 o 1.234,56, sin símbolos.') from None
    p=preparar_precio(dict(base_precio=base,precio_bulto=datos['precio_proveedor'] if base=='bulto' else None,precio_unitario=datos['precio_proveedor'] if base=='unitario' else None,cantidad_bulto=datos.get('cantidad_bulto'),medidas_origen=datos.get('medidas_origen')))
    return dict(moneda=moneda,precio_unitario_centavos=p['unitario_centavos'],cantidad_bulto=p['cantidad_bulto'] or None,precio_bulto_centavos=p['bulto_centavos'],base_precio=base,medidas_origen=p['medidas_origen'])

def _igual(c,plan):
    if c is None:return False
    for k,v in plan.items():
        esperado=Decimal(v) if k=='cantidad_bulto' and v is not None else v
        if getattr(c,k)!=esperado:return False
    return True


def revisar(filas,campos,p,org,unidad,session):
    listo(session);proveedor_valido(p,org,unidad,session)
    if not campos or any(c not in CAMPOS for c in campos):raise ValueError('Elegí campos de precio válidos.')
    cat,insumos=catalogo(org,unidad,p.id,session);vista=[];ignoradas=0;vistas=set()
    por_sku=defaultdict(list);previas=defaultdict(list)
    for ref in cat.values():
        for alias in {insumos[ref['insumo_id']].codigo.casefold(),*ref['skus']}:por_sku[alias].append(ref)
    ids={ref['vinculo_id'] for ref in cat.values() if ref['vinculo_id']}
    if ids:
        for c in session.query(C).filter(C.vinculo_id.in_(ids),C.vigente.is_(True)):previas[c.vinculo_id].append(c)
    for fila in filas:
        v=fila['valores'];codigo=str(v.get('codigo_proveedor') or '').strip();sku=str(v.get('sku') or '').strip()
        ref=cat.get(codigo.upper()) if codigo else None
        if ref is None and sku and not codigo:
            opciones=por_sku.get(sku.casefold(),[])
            if len(opciones)==1:ref=opciones[0]
        if ref is None:ignoradas+=1;continue
        if len(vista)>=500:raise ValueError('La lista supera 500 coincidencias. Dividila en bloques de hasta 500.')
        i=insumos[ref['insumo_id']];r=dict(numero=fila['numero'],codigo=ref['codigo'],insumo_id=i.id,material=i.nombre,valores={c:v[c] for c in campos if c in v},errores=[],vinculo_id=ref['vinculo_id'])
        for clave in ('_codimat','_error_codimat'):
            if clave in v:r['valores'][clave]=v[clave]
        try:
            if v.get('_error_codimat'):raise ValueError(v['_error_codimat'][0])
            if sku and i.codigo.casefold()!=sku.casefold() and sku.casefold() not in ref['skus']:raise ValueError('SKU/código de material y código de proveedor no coinciden.')
            if fila.get('formulas'):raise ValueError('Pegá valores, no fórmulas, en los campos seleccionados.')
            moneda=str(v.get('moneda_proveedor') if 'moneda_proveedor' in campos and v.get('moneda_proveedor') else 'ARS').upper()
            # Una moneda omitida sólo se infiere si hay una única cotización previa.
            anteriores=previas.get(ref['vinculo_id'],[])
            if 'moneda_proveedor' not in r['valores'] and anteriores:
                if len(anteriores)!=1:raise ValueError('Seleccioná Moneda proveedor: hay cotizaciones en varias monedas.')
                moneda=anteriores[0].moneda
            actual=next((c for c in anteriores if c.moneda==moneda),None)
            if actual is None and not r['valores'].get('moneda_proveedor'):raise ValueError('Completá y seleccioná Moneda proveedor para la primera cotización.')
            r['plan']=_plan(r['valores']|{'moneda_proveedor':moneda},actual)
            if (i.id,moneda) in vistas:raise ValueError('El mismo material y moneda aparecen más de una vez.')
            vistas.add((i.id,moneda))
            r['anterior']=actual.precio_unitario_centavos if actual else None;r['version_actual']=actual.id if actual else None
            r['cambia']=not _igual(actual,r['plan'])
            r['huella']=_firma([i.id,i.codigo,i.nombre,i.activo,i.unidad_negocio_id,ref,actual.id if actual else None,_datos(actual)])
        except ValueError as e:r['errores']=[str(e)];r['cambia']=False
        vista.append(r)
    return dict(filas=vista,ignoradas=ignoradas,campos=list(campos))

def firmar(vista,p,org,unidad,usuario,secreto):
    if any(f['errores'] for f in vista['filas']):raise ValueError('Corregí las filas con errores antes de confirmar.')
    # Sólo coincidencias revisadas: no incluir miles de filas ignoradas en el token.
    return URLSafeTimedSerializer(secreto,salt=SALT).dumps(dict(org=org,unidad=unidad,proveedor=p,usuario=usuario,vista=vista))

def _guardar_cotizacion(l,plan,referencia,session):
    actual=_actual(l.id,plan['moneda'],session)
    if _igual(actual,plan):return actual
    if actual:actual.vigente=False;session.flush()
    ultima=session.query(C.numero_version).filter_by(vinculo_id=l.id,moneda=plan['moneda']).order_by(C.numero_version.desc()).first()
    c=C(vinculo_id=l.id,numero_version=(ultima[0] if ultima else 0)+1,referencia=referencia,**(plan|{'cantidad_bulto':Decimal(plan['cantidad_bulto']) if plan['cantidad_bulto'] else None}))
    session.add(c);session.flush();return c

def confirmar(token,p,org,unidad,usuario,secreto,session):
    try:datos=URLSafeTimedSerializer(secreto,salt=SALT).loads(token,max_age=1800)
    except (BadSignature,SignatureExpired):raise ValueError('La revisión venció o no es válida. Volvé a importar.') from None
    if [datos.get(k) for k in ['org','unidad','proveedor','usuario']]!=[org,unidad,p.id,usuario]:raise ValueError('La revisión pertenece a otro usuario, proveedor o unidad.')
    anterior=datos['vista'];listo(session);proveedor_valido(p,org,unidad,session)
    config=None
    if 'codimat' in anterior:
        from services.listas_codimat import configuracion
        from models.listas_proveedores_compra import ConfiguracionListaProveedor
        session.query(type(p)).filter_by(id=p.id,organizacion_id=org).with_for_update().one()
        config=configuracion(org,unidad,p.id,session,bloquear=True)
        if (config.reglas if config else None)!=anterior['codimat']['config_anterior']:raise ValueError('Las bonificaciones cambiaron. Volvé a revisar la lista.')
    # Bloquear material/vínculos antes de releer para detectar revisiones antiguas.
    ids=sorted({f['insumo_id'] for f in anterior['filas']})
    session.query(I).filter(I.id.in_(ids),I.organizacion_id==org,I.unidad_negocio_id==unidad).order_by(I.id).with_for_update().all()
    session.query(L).filter(L.insumo_id.in_(ids),L.proveedor_id==p.id,L.unidad_negocio_id==unidad).order_by(L.id).with_for_update().all()
    filas=[dict(numero=f['numero'],valores=f['valores']|{'codigo_proveedor':f['codigo']},formulas=[]) for f in anterior['filas']]
    nueva=revisar(filas,anterior['campos'],p,org,unidad,session)
    if _firma(nueva['filas'])!=_firma(anterior['filas']):raise ValueError('Cambió un vínculo, material o cotización. Volvé a revisar; no se guardó nada.')
    n=0
    for f in nueva['filas']:
        if not f['cambia']:continue
        l=vincular(_material(f['insumo_id'],org,unidad,session),p,f['codigo'],org,unidad,session)
        cotizacion=_guardar_cotizacion(l,f['plan'],str(anterior.get('referencia') or 'Importación de lista')[:120],session)
        if f['valores'].get('_codimat'):
            from models.listas_proveedores_compra import CalculoCotizacionProveedor
            session.add(CalculoCotizacionProveedor(cotizacion_id=cotizacion.id,datos=f['valores']['_codimat']))
        n+=1
    if 'codimat' in anterior:
        if config is None:
            config=ConfiguracionListaProveedor(organizacion_id=org,unidad_negocio_id=unidad,proveedor_id=p.id)
            session.add(config)
        config.reglas=anterior['codimat']['reglas']
        session.flush()
    return n

def usar_en_costo(cotizacion,p,org,unidad,version_esperada,session,usuario):
    from services.fuentes_costo_productivo import registrar_precio_insumo
    from services.insumos_presentacion import guardar,guardar_precio
    listo(session);proveedor_valido(p,org,unidad,session)
    c=session.query(C).join(L,L.id==C.vinculo_id).filter(C.id==cotizacion,L.organizacion_id==org,L.unidad_negocio_id==unidad,L.proveedor_id==p.id).first()
    if c is None:raise ValueError('La cotización no pertenece al proveedor de esta unidad.')
    l=session.query(L).filter_by(id=c.vinculo_id).one()
    i=session.query(I).filter_by(id=l.insumo_id,organizacion_id=org,unidad_negocio_id=unidad).with_for_update().first()
    session.query(L).filter_by(id=l.id).with_for_update().one()
    if i is None or not i.activo:raise ValueError('El material no pertenece a la unidad activa o está inactivo.')
    session.refresh(c)
    if not c.vigente:raise ValueError('La cotización cambió. Elegí la versión vigente.')
    actual=session.query(V).filter_by(insumo_id=i.id,moneda=c.moneda,vigente=True).populate_existing().with_for_update().first()
    if str(actual.id if actual else '')!=str(version_esperada or ''):raise ValueError('El costo cambió. Recargá antes de aplicar la cotización.')
    if actual and actual.id==c.precio_insumo_version_id:return actual
    datos=dict(base_precio=c.base_precio,cantidad_bulto=str(c.cantidad_bulto) if c.cantidad_bulto is not None else '',medidas_origen=c.medidas_origen,precio_unitario=str(Decimal(c.precio_unitario_centavos)/100) if c.base_precio=='unitario' else None,precio_bulto=str(Decimal(c.precio_bulto_centavos)/100) if c.base_precio=='bulto' else None)
    guardar(i,datos,session,org)
    v=registrar_precio_insumo(i,moneda=c.moneda,precio_unitario_centavos=c.precio_unitario_centavos,proveedor_referencia=p.razon_social,comprobante_referencia=c.referencia,observacion='Cotización de Compras aplicada explícitamente al costo.',creado_por_usuario_id=usuario,InsumoPrecioVersion=V,db_session=session,commit=False)
    guardar_precio(v,i,datos,session,org);c.precio_insumo_version_id=v.id;session.flush();return v

def plantilla():
    from openpyxl import Workbook
    w=Workbook();s=w.active;s.title='Productos';s.append([lector.etiqueta(c) for c in ['codigo_proveedor','sku',*CAMPOS]])
    for col in s.columns:s.column_dimensions[col[0].column_letter].width=30
    s.freeze_panes='A2'
    a=w.create_sheet('Cómo usar')
    for t in ['Pegá la lista del proveedor en Productos, sin cambiar encabezados.','Código proveedor identifica el vínculo. SKU es opcional: código interno del material.','Si usás vínculos de Productos previos, su fuente debe estar asignada explícitamente a esta unidad.','Tildá sólo los campos que querés actualizar. Vacíos conservan datos; cero es un precio válido.','Primera cotización: completá Precio proveedor sin IVA, Cotización proveedor (unitario/bulto) y Moneda proveedor.','Bulto requiere Cantidad por bulto. Los precios son sin IVA.','Artículos sin vínculo se ignoran; no se crean productos ni materiales.','Confirmar guarda cotizaciones independientes. Para cambiar el costo, elegí Usar en costo después.']:a.append([t])
    for col in ['A','B']:
        s.column_dimensions[col].number_format='@'
        for row in range(2,502):s[f'{col}{row}'].number_format='@'
    b=BytesIO();w.save(b);b.seek(0);return b
