"""Alias de lectura para el selector; conserva la identidad del insumo/costo."""
from sqlalchemy import inspect


def enriquecer_insumos(recursos, session, organizacion_id):
    from models.fuentes_costo_productivo import InsumoProductivo, InsumoPrecioVersion
    ids = [r['id'] for r in recursos]
    salida = {r['id']: dict(r, skus=[], codigos_proveedor=[], proveedores=[]) for r in recursos}
    if not ids:
        return []
    # El recurso base y todas sus relaciones deben pertenecer al tenant.
    permitidos = {r[0] for r in session.query(InsumoProductivo.id).filter(InsumoProductivo.id.in_(ids), InsumoProductivo.organizacion_id == organizacion_id).all()}
    salida = {i:r for i,r in salida.items() if i in permitidos}
    for precio in session.query(InsumoPrecioVersion).join(InsumoProductivo, InsumoProductivo.id == InsumoPrecioVersion.insumo_id).filter(
            InsumoProductivo.organizacion_id == organizacion_id, InsumoProductivo.id.in_(permitidos), InsumoPrecioVersion.vigente.is_(True)):
        nombre = str(precio.proveedor_referencia or '').strip()
        if nombre and nombre not in salida[precio.insumo_id]['proveedores']:
            salida[precio.insumo_id]['proveedores'].append(nombre)
    i = inspect(session.connection())
    def tiene(tabla, columnas):
        return i.has_table(tabla) and set(columnas) <= {c['name'] for c in i.get_columns(tabla)}
    if not tiene('producto_ficha_maestra', ('producto_id','organizacion_id','insumo_id')):
        return list(salida.values())
    from models.producto import Producto
    from models.producto_ficha_maestra import ProductoFichaMaestra as Ficha
    enlaces = session.query(Producto.id, Producto.sku, Ficha.insumo_id).join(Ficha, Ficha.producto_id == Producto.id).filter(
        Producto.organizacion_id == organizacion_id, Ficha.organizacion_id == organizacion_id, Ficha.insumo_id.in_(permitidos)).all()
    productos = {}
    for producto_id, sku, insumo_id in enlaces:
        productos[producto_id] = insumo_id
        if sku and sku not in salida[insumo_id]['skus']:
            salida[insumo_id]['skus'].append(sku)
    if productos and tiene('producto_proveedor', ('producto_id','organizacion_id','proveedor_id','codigo')) and tiene('proveedor_compra', ('id','organizacion_id','razon_social')):
        from models.producto_datos_generales import ProductoProveedor
        from models.compras import ProveedorCompra
        for producto_id, codigo, razon_social in session.query(ProductoProveedor.producto_id, ProductoProveedor.codigo, ProveedorCompra.razon_social).join(ProveedorCompra, ProveedorCompra.id == ProductoProveedor.proveedor_id).filter(
                ProductoProveedor.organizacion_id == organizacion_id, ProveedorCompra.organizacion_id == organizacion_id, ProductoProveedor.producto_id.in_(productos)):
            destino = salida[productos[producto_id]]
            dato = {'codigo':codigo, 'proveedor':razon_social}
            if codigo and dato not in destino['codigos_proveedor']:
                destino['codigos_proveedor'].append(dato)
            if razon_social not in destino['proveedores']:
                destino['proveedores'].append(razon_social)
    return list(salida.values())
