"""Grilla de consulta interna: precios y existencias, sin escrituras."""
from decimal import Decimal, ROUND_HALF_UP
import csv
import json
from types import SimpleNamespace
from io import BytesIO, StringIO


def importe_visible(precio, con_iva):
    if precio is None:
        return None
    if con_iva:
        return precio['final']
    return precio['neto']


def disponible(existencias):
    if not existencias or any(not e.control_activo for e in existencias):
        return None
    return sum(e.stock_actual-e.stock_reservado-e.stock_bloqueado for e in existencias)


def filtrar_filas(filas, filtros):
    salida=[]
    for fila in filas:
        if any(str(filtros.get(k,'')).strip().casefold() not in str(fila.get(k,'')).casefold()
               for k in ('codigo','nombre','rubro','subrubro','marca','proveedor')):
            continue
        stock=fila['stock']
        modo=filtros.get('stock','todos')
        if modo=='con' and (stock is None or stock<=0): continue
        if modo=='sin' and (stock is None or stock>0): continue
        if modo=='pendiente' and stock is not None: continue
        if filtros.get('sin_precio') and any(p is not None for p in fila['precios'].values()): continue
        salida.append(fila)
    return salida


def consultar(organizacion_id, unidad_id, filtros):
    from sqlalchemy import inspect
    from extensions import db
    from models.producto import Producto
    from models.producto_ficha_maestra import ProductoFichaMaestra
    from models.producto_datos_generales import ProductoDatosGenerales, ProductoProveedor
    from models.compras import ProveedorCompra
    from models.perfil_costeo_producto import PerfilCosteoProducto
    from models.catalogo import Catalogo
    from models.catalogo_producto import CatalogoProducto
    from models.costo_producto_version import CostoProductoVersion
    from models.lista_precio import ListaPrecio
    from models.lista_precio_item import ListaPrecioItem
    from models.regla_canal import ReglaCanalVersion
    from models.existencia_sucursal import ExistenciaSucursal
    from models.sucursal_operativa import SucursalOperativa
    from models.inventario_saas import ItemInventario
    from services.precio_mayorista_producto import preparar_mayoristas
    from services.enlace_economico_producto import construir_enlaces
    tablas=set(inspect(db.session.get_bind()).get_table_names())
    def todos(modelo, **kw):
        if modelo.__tablename__ not in tablas: return []
        return modelo.query.filter_by(organizacion_id=organizacion_id, **kw).all()
    perfiles=todos(PerfilCosteoProducto,unidad_negocio_id=unidad_id)
    costos=todos(CostoProductoVersion,unidad_negocio_id=unidad_id)
    catalogos=todos(Catalogo,unidad_negocio_id=unidad_id)
    catids=[c.id for c in catalogos]
    inclusiones=CatalogoProducto.query.filter(CatalogoProducto.catalogo_id.in_(catids)).all() if catids and CatalogoProducto.__tablename__ in tablas else []
    ids={p.producto_id for p in perfiles}|{i.producto_id for i in inclusiones}|{c.producto_id for c in costos}
    productos=Producto.query.filter(Producto.organizacion_id==organizacion_id,Producto.id.in_(ids)).all() if ids else []
    generales={g.producto_id:g for g in todos(ProductoDatosGenerales) if g.producto_id in ids}
    fichas={g.producto_id:g for g in todos(ProductoFichaMaestra) if g.producto_id in ids}
    proveedores={p.id:p.razon_social for p in todos(ProveedorCompra)}
    proveedores_producto={pid:[] for pid in ids}
    for vinculo in todos(ProductoProveedor):
        if vinculo.producto_id in ids and vinculo.proveedor_id in proveedores:
            proveedores_producto[vinculo.producto_id].append(proveedores[vinculo.proveedor_id])
    listas=sorted(todos(ListaPrecio,unidad_negocio_id=unidad_id),key=lambda l:(l.tipo!='mayorista',l.nombre))
    listas=[l for l in listas if l.estado not in ('archivado','cancelado') and l.moneda=='ARS']
    listaids=[l.id for l in listas]
    reglas=ReglaCanalVersion.query.filter(ReglaCanalVersion.lista_precio_id.in_(listaids)).all() if listaids and ReglaCanalVersion.__tablename__ in tablas else []
    items=ListaPrecioItem.query.filter(ListaPrecioItem.lista_precio_id.in_(listaids),ListaPrecioItem.vigente.is_(True)).all() if listaids and ListaPrecioItem.__tablename__ in tablas else []
    _,simulaciones,bloqueos=construir_enlaces(organizacion_id=organizacion_id,unidad_negocio_id=unidad_id,
        costos=costos,inclusiones=inclusiones,reglas_economicas=[],reglas_canal=reglas,
        perfiles=perfiles,modelo_costo=CostoProductoVersion,datos_productos=generales)
    columnas=[dict(id='base',nombre='Mayorista base',moneda='ARS')]+[dict(id=str(l.id),nombre=l.nombre,moneda=l.moneda) for l in listas]
    elegida=str(filtros.get('lista',''))
    if elegida:
        if elegida not in {c['id'] for c in columnas}: raise ValueError('La lista no pertenece a esta unidad.')
        columnas=[c for c in columnas if c['id']==elegida]
    bases={f['costo'].producto_id:f for f in preparar_mayoristas(costos,generales)}
    precios={}
    for f in simulaciones:
        p=f['objetivo']['precio_final_centavos'];iva=Decimal(str(generales[f['costo'].producto_id].iva_pct))
        neto=int((Decimal(p)/(1+iva/100)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        precios[(f['costo'].producto_id,str(f['regla_canal'].lista_precio_id))]=dict(final=p,neto=neto,estado='Calculado · no guardado')
    inc_por_id={i.id:i for i in inclusiones}
    guardados={}
    for item in items:
        inclusion=inc_por_id.get(item.catalogo_producto_id)
        if inclusion:
            clave=(inclusion.producto_id,str(item.lista_precio_id))
            guardados.setdefault(clave,[]).append(item)
    for clave, registros in guardados.items():
        if len(registros)==1:
            item=registros[0]
            precios[clave]=dict(final=item.precio_final_centavos,neto=item.precio_elegido_centavos,estado='Precio guardado vigente')
        else:
            precios[clave]=None
    sucursales=sorted(todos(SucursalOperativa),key=lambda s:s.nombre)
    sucids={s.id for s in sucursales}
    deposito=str(filtros.get('deposito',''))
    if deposito:
        if not deposito.isdigit() or int(deposito) not in sucids: raise ValueError('Depósito no válido para esta organización.')
        sucids={int(deposito)}
    inventario=[i for i in todos(ItemInventario) if i.producto_id in ids and (i.catalogo_producto_id is None or i.catalogo_producto_id in inc_por_id)]
    existencias=[e for e in todos(ExistenciaSucursal) if e.producto_id in ids and e.sucursal_operativa_id in sucids]
    filas=[]
    for producto in sorted(productos,key=lambda p:p.sku):
        ficha=fichas.get(producto.id);g=generales.get(producto.id)
        base=bases.get(producto.id);valores={}
        for col in columnas:
            if col['id']=='base':
                p=base['precio'] if base else None
                valores['base']=dict(final=p['precio_final_centavos'],neto=p['neto_centavos'],estado='Vista previa · costo '+('vigente' if base['costo'].vigente else 'preparatorio')) if p else None
            else:valores[col['id']]=precios.get((producto.id,col['id']))
        unidades=[i for i in inventario if i.producto_id==producto.id]
        variantes=[i for i in unidades if i.sku!=producto.sku]
        skus={producto.sku}|{i.sku for i in variantes}
        for inclusion in inclusiones:
            if inclusion.producto_id!=producto.id: continue
            try: declaradas=json.loads(inclusion.variantes_json or '[]')
            except (ValueError,TypeError): declaradas=[]
            if not isinstance(declaradas,list): continue
            for v in declaradas:
                if not isinstance(v,dict): continue
                sku=str(v.get('sku','')).strip()
                if sku and sku not in skus:
                    variantes.append(SimpleNamespace(id=None,sku=sku,
                        nombre=(ficha.nombre if ficha else producto.descripcion)+' · '+str(v.get('opciones',''))))
                    skus.add(sku)
        registros=[(producto.sku,ficha.nombre if ficha else producto.descripcion,None)]+[(i.sku,i.nombre,i) for i in variantes]
        for codigo,nombre,variante in registros:
            ex=[e for e in existencias if e.producto_id==producto.id and (variante.id is not None and e.item_inventario_id==variante.id if variante else e.item_inventario_id is None or any(i.id==e.item_inventario_id and i.sku==producto.sku for i in unidades))]
            # No se copia el precio del producto padre a una variante sin precio propio.
            pv=valores if variante is None else {col['id']:None for col in columnas}
            filas.append(dict(codigo=codigo,nombre=nombre,rubro=g.rubro if g else '',subrubro=g.subrubro if g else '',marca=g.marca if g else '',proveedor=' · '.join(proveedores_producto[producto.id]),stock=disponible(ex),precios=pv,
                motivo=(base['error'] if base else 'Sin costo guardado') if variante is None else 'Variante: precio propio pendiente'))
    filas=filtrar_filas(filas,filtros)
    return dict(filas=filas,columnas=columnas,listas=listas,sucursales=sucursales,bloqueos=bloqueos)


def exportar(filas,columnas,con_iva):
    texto=StringIO();writer=csv.writer(texto,delimiter=';')
    writer.writerow(['Código','Producto','Stock disponible']+[c['nombre'] for c in columnas])
    for f in filas:
        # Evita fórmulas al abrir el CSV en una planilla.
        seguro=lambda v: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
        writer.writerow([seguro(f['codigo']),seguro(f['nombre']),f['stock'] if f['stock'] is not None else 'Sin control']+[
            ('%.2f'%(importe_visible(f['precios'].get(c['id']),con_iva)/100)).replace('.',',') if f['precios'].get(c['id']) else '' for c in columnas])
    return BytesIO(texto.getvalue().encode('utf-8-sig'))
