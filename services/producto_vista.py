"""Ficha de consulta del Producto existente. Solo lecturas, sin cálculos de negocio."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import column, inspect, select, table
from services.productos_ficha_maestra import construir_filas


def numero(valor):
    if valor is None or valor == '': return '—'
    try:
        n = Decimal(str(valor))
        if not n.is_finite(): return '—'
        s = format(n, ',.6f').rstrip('0').rstrip('.')
        return s.replace(',', '_').replace('.', ',').replace('_', '.')
    except (InvalidOperation, ValueError): return str(valor)


def dinero(centavos, moneda='ARS'):
    if centavos is None: return '—'
    s = format(Decimal(str(centavos)) / 100, ',.2f')
    return f"{moneda} {s.replace(',', '_').replace('.', ',').replace('_', '.')}"


def fecha_local(valor):
    if not valor: return '—'
    try:
        d = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor).replace('Z', '+00:00'))
        return d.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/Argentina/Buenos_Aires')).strftime('%d/%m/%Y %H:%M') if d.tzinfo is None else d.astimezone(ZoneInfo('America/Argentina/Buenos_Aires')).strftime('%d/%m/%Y %H:%M')
    except ValueError: return str(valor)


def obtener_vista(producto, session, organizacion_id):
    if producto.organizacion_id != organizacion_id:
        raise ValueError('El producto no pertenece a la organización.')
    _, filas = construir_filas([producto], session, organizacion_id)
    fila = filas[0]
    a = fila['adicionales']
    inspector = inspect(session.connection())
    cache = {}

    def t(nombre, campos):
        # Nombres de tablas/campos constantes del servidor. Tolera módulos no preparados.
        if nombre not in cache:
            cache[nombre] = {c['name'] for c in inspector.get_columns(nombre)} if inspector.has_table(nombre) else set()
        return table(nombre, *[column(c) for c in campos]) if set(campos) <= cache[nombre] else None

    def leer(tabla, *condiciones):
        return [dict(r) for r in session.execute(select(tabla).where(*condiciones)).mappings()] if tabla is not None else []

    u = t('unidad_negocio', ['id','organizacion_id','nombre'])
    unidades = {r['id']:r['nombre'] for r in leer(u, u.c.organizacion_id == organizacion_id)} if u is not None else {}
    unidad = lambda ident: 'General' if ident is None else unidades.get(ident, 'Unidad no disponible')
    p = t('proveedor_compra', ['id','organizacion_id','codigo','razon_social','cuit','email','telefono','domicilio','localidad','provincia','codigo_postal','persona_contacto','estado'])
    proveedores = {r['id']:r for r in leer(p, p.c.organizacion_id == organizacion_id, p.c.id.in_([r['proveedor_id'] for r in a.get('proveedores',[])]))} if p is not None else {}
    contacto = t('proveedor_contacto', ['proveedor_id','organizacion_id','telefono_contacto'])
    contactos = {r['proveedor_id']:r['telefono_contacto'] for r in leer(contacto, contacto.c.organizacion_id == organizacion_id, contacto.c.proveedor_id.in_(proveedores))} if contacto is not None else {}
    proveedores_vista = [dict(proveedores.get(r['proveedor_id'], {'razon_social':'Proveedor no disponible'}), codigo_externo=r['codigo'], telefono_contacto=contactos.get(r['proveedor_id'],'')) for r in a.get('proveedores',[])]
    s = t('sucursal_operativa', ['id','organizacion_id','nombre','activa'])
    sucursales = {r['id']:r for r in leer(s,s.c.organizacion_id == organizacion_id)} if s is not None else {}
    ubicaciones = {g:[sucursales.get(ident, {'nombre':'Ubicación no disponible','activa':False}) for ident in a.get(g,[])] for g in ('sucursales','depositos')}
    fuentes = {}
    referencias = {g:set() for g in ('insumos','operaciones','maquinas','fijos')}
    if fila['datos'].get('insumo_id'):
        referencias['insumos'].add(fila['datos']['insumo_id'])
    for receta in fila['producciones']:
        for grupo, clave in [('insumos','insumo_id'),('operaciones','empleado_id'),('maquinas','maquina_id'),('fijos','costo_fijo_id')]:
            referencias[grupo].update(r[clave] for r in receta[grupo])
        fisico = (receta.get('despiece') or {}).get('datos',{})
        referencias['insumos'].update(r['insumo_id'] for r in fisico.get('piezas',[]))
        if fisico.get('tarifa_id'): referencias['operaciones'].add(fisico['tarifa_id'])
    for grupo, (nombre, campos) in {
        'insumos':('insumo_productivo',['id','organizacion_id','codigo','nombre','unidad_medida']),
        'operaciones':('empleado_productivo',['id','organizacion_id','codigo','nombre']),
        'maquinas':('maquina_productiva',['id','organizacion_id','codigo','nombre']),
        'fijos':('costo_fijo_productivo',['id','organizacion_id','codigo','nombre']),
    }.items():
        fuente = t(nombre, campos)
        fuentes[grupo] = {r['id']:r for r in leer(fuente, fuente.c.organizacion_id == organizacion_id, fuente.c.id.in_(referencias[grupo]))} if fuente is not None else {}
    fabricaciones = []
    for receta in fila['producciones']:
        d = dict(receta, unidad=unidad(receta['unidad_id']))
        for grupo, clave in [('insumos','insumo_id'),('operaciones','empleado_id'),('maquinas','maquina_id'),('fijos','costo_fijo_id')]:
            d[grupo] = [dict(r, recurso=fuentes[grupo].get(r[clave], {'nombre':'Recurso no disponible','codigo':'—','unidad_medida':'—'})) for r in receta[grupo]]
        despiece = receta.get('despiece')
        d['piezas'] = [dict(r, recurso=fuentes['insumos'].get(r['insumo_id'], {'nombre':'Material no disponible','codigo':'—','unidad_medida':'—'})) for r in (despiece or {}).get('datos',{}).get('piezas',[])]
        d['tareas'] = (despiece or {}).get('datos',{}).get('tareas',[])
        d['despiece_actual'] = despiece['actual'] if despiece else None
        d['tarifa'] = fuentes['operaciones'].get((despiece or {}).get('datos',{}).get('tarifa_id'),{}).get('nombre')
        fabricaciones.append(d)
    # Costos guardados: no se recalculan ni se activa ninguna versión.
    cv = t('costo_producto_version', ['id','organizacion_id','producto_id','unidad_negocio_id','moneda','tipo','numero_version','costo_total_centavos','estado','vigente','fecha_creacion','creado_por_username','observacion','vigente_desde','vigente_hasta'])
    costos = leer(cv,cv.c.organizacion_id == organizacion_id,cv.c.producto_id == producto.id) if cv is not None else []
    costos.sort(key=lambda c:c['id'], reverse=True)
    cd = t('costo_producto_detalle',['costo_producto_version_id','orden','tipo','codigo','concepto','cantidad','unidad_medida','costo_unitario_centavos','porcentaje_merma','subtotal_centavos','observacion'])
    detalles = leer(cd,cd.c.costo_producto_version_id.in_([c['id'] for c in costos])) if cd is not None else []
    for c in costos:
        c['unidad']=unidad(c['unidad_negocio_id'])
        c['detalles']=sorted([r for r in detalles if r['costo_producto_version_id']==c['id']],key=lambda r:r['orden'])
    ex = t('existencia_sucursal',['organizacion_id','producto_id','sucursal_operativa_id','stock_actual','stock_reservado','stock_bloqueado','stock_transito','stock_minimo','stock_maximo','control_activo'])
    stock = leer(ex,ex.c.organizacion_id == organizacion_id,ex.c.producto_id == producto.id) if ex is not None else []
    for r in stock:
        r['ubicacion']=sucursales.get(r['sucursal_operativa_id'],{}).get('nombre','Ubicación no disponible')
        r['disponible']=r['stock_actual']-r['stock_reservado']-r['stock_bloqueado']
    # Listas y publicaciones ya registradas, vinculadas por ID; nunca por SKU textual.
    cp = t('catalogo_producto',['id','organizacion_id','producto_id'])
    lp = t('lista_precio',['id','organizacion_id','nombre','moneda','unidad_negocio_id','estado'])
    li = t('lista_precio_item',['id','lista_precio_id','catalogo_producto_id','numero_version','costo_base_centavos','precio_elegido_centavos','impuestos_centavos','precio_final_centavos','margen_pct','impuesto_pct','estado','vigente','fecha_creacion'])
    precios=[]
    if all(x is not None for x in (cp,lp,li)):
        q=select(li,lp.c.nombre.label('lista'),lp.c.moneda,lp.c.unidad_negocio_id).select_from(li.join(cp,li.c.catalogo_producto_id==cp.c.id).join(lp,li.c.lista_precio_id==lp.c.id)).where(cp.c.organizacion_id==organizacion_id,cp.c.producto_id==producto.id,lp.c.organizacion_id==organizacion_id).order_by(li.c.id.desc())
        precios=[dict(r,unidad=unidad(r['unidad_negocio_id'])) for r in session.execute(q).mappings()]
    m=t('mapeo_publicacion_canal',['organizacion_id','vinculo_canal_comercial_id','catalogo_producto_id','canal','publicacion_externa_id','variante_externa_id','sku_externo','estado','identidad_verificada','permite_sincronizar'])
    v=t('vinculo_canal_comercial',['id','organizacion_id','nombre','unidad_negocio_id'])
    canales=[]
    if all(x is not None for x in (cp,m,v)):
        q=select(m,v.c.nombre.label('cuenta'),v.c.unidad_negocio_id).select_from(m.join(cp,m.c.catalogo_producto_id==cp.c.id).join(v,m.c.vinculo_canal_comercial_id==v.c.id)).where(m.c.organizacion_id==organizacion_id,cp.c.organizacion_id==organizacion_id,cp.c.producto_id==producto.id,v.c.organizacion_id==organizacion_id)
        canales=[dict(r,unidad=unidad(r['unidad_negocio_id'])) for r in session.execute(q).mappings()]
    o=t('observacion_comercial_canal',['organizacion_id','catalogo_producto_id','unidad_negocio_id','lista_precio_id','tipo','cuenta_codigo','referencia_publicacion','precio_publicado_centavos','comision_pct','cargo_fijo_centavos','costo_envio_centavos','origen','fecha_observacion'])
    observaciones=[]
    if all(x is not None for x in (cp,o,lp)):
        q=select(o,lp.c.moneda,lp.c.nombre.label('lista')).select_from(o.join(cp,o.c.catalogo_producto_id==cp.c.id).join(lp,o.c.lista_precio_id==lp.c.id)).where(o.c.organizacion_id==organizacion_id,cp.c.organizacion_id==organizacion_id,cp.c.producto_id==producto.id,lp.c.organizacion_id==organizacion_id).order_by(o.c.fecha_observacion.desc())
        observaciones=[dict(r,unidad=unidad(r['unidad_negocio_id'])) for r in session.execute(q).mappings()]
    return dict(fila=fila, proveedores=proveedores_vista, ubicaciones=ubicaciones, fabricaciones=fabricaciones,
        combos=[dict(r,unidad=unidad(r['unidad_combo_id'])) for r in fila['composiciones']], costos=costos, stock=stock,
        precios=precios, canales=canales, observaciones=observaciones,
        vinculo_insumo=fuentes['insumos'].get(fila['datos'].get('insumo_id')),
        disponibles={'costos':cv is not None,'stock':ex is not None,'precios':all(x is not None for x in (cp,lp,li)),'canales':all(x is not None for x in (cp,m,v))})
