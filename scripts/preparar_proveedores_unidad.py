"""Migración explícita: conserva proveedores, vincula sólo compras ya documentadas."""
from sqlalchemy import inspect, text
from models.proveedor_unidad import ProveedorUnidad


def preparado(conexion):
    i = inspect(conexion)
    return i.has_table('proveedor_unidad') and set(ProveedorUnidad.__table__.c.keys()) <= {c['name'] for c in i.get_columns('proveedor_unidad')}


def preparar(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.compras import ProveedorCompra
    with engine.begin() as c:
        i = inspect(c)
        if not all(i.has_table(t) for t in ('organizacion','unidad_negocio','proveedor_compra','orden_compra')):
            raise ValueError('Faltan tablas base de Compras.')
        if i.has_table('proveedor_unidad') and not preparado(c):
            raise ValueError('El esquema de proveedores por unidad necesita revisión.')
        ProveedorUnidad.__table__.create(c, checkfirst=True)
        # Evidencia de pertenencia, sin atribuir proveedores sin compras por descarte.
        c.execute(text('''INSERT INTO proveedor_unidad (organizacion_id, proveedor_id, unidad_negocio_id, estado)
            SELECT DISTINCT o.organizacion_id, o.proveedor_id, o.unidad_negocio_id, p.estado
            FROM orden_compra o JOIN proveedor_compra p ON p.id=o.proveedor_id AND p.organizacion_id=o.organizacion_id
            JOIN unidad_negocio u ON u.id=o.unidad_negocio_id AND u.organizacion_id=o.organizacion_id
            WHERE NOT EXISTS (SELECT 1 FROM proveedor_unidad v WHERE v.proveedor_id=o.proveedor_id AND v.unidad_negocio_id=o.unidad_negocio_id)'''))
    return 'Proveedores preparados por unidad. Sin duplicar fichas ni modificar documentos. Los proveedores sin compras requieren vinculación explícita por código o CUIT.'


def main():
    import argparse
    import os
    from sqlalchemy import create_engine
    parser = argparse.ArgumentParser()
    parser.add_argument('--staging', action='store_true', required=True)
    parser.parse_args()
    if os.environ.get('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:
        raise SystemExit('Se requiere laboratorio desconectado.')
    rama = os.environ.get('RENDER_GIT_BRANCH','')
    if rama and rama != 'integracion-saas-2026-09':
        raise SystemExit('Se requiere la rama de integración.')
    servicio = os.environ.get('RENDER_EXTERNAL_URL','')
    if servicio and 'staging' not in servicio:
        raise SystemExit('Se requiere el servicio staging.')
    url = os.environ.get('DATABASE_URL','')
    if not url: raise SystemExit('No se encontró la base del servicio.')
    if url.startswith('postgres://'): url='postgresql://'+url[len('postgres://'):]
    engine=create_engine(url)
    try: print(preparar(engine))
    finally: engine.dispose()


if __name__ == '__main__': main()
