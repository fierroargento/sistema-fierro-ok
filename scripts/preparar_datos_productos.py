"""Preparación aditiva del alta completa de Productos, solo en staging."""
import argparse
import os
from sqlalchemy import create_engine, inspect


def preparar(engine):
    from scripts.preparar_ficha_productos import preparar as preparar_ficha
    from models.organizacion import Organizacion
    from models.producto import Producto
    from models.compras import ProveedorCompra
    from models.sucursal_operativa import SucursalOperativa
    from models.producto_datos_generales import TABLAS_DATOS_PRODUCTO
    with engine.begin() as conexion:
        inspector=inspect(conexion)
        if not all(inspector.has_table(t) for t in ('organizacion','producto','insumo_productivo','proveedor_compra','sucursal_operativa')):
            raise ValueError('Faltan tablas base de Productos, Proveedores o ubicaciones. No se preparó la ampliación.')
        nuevas=[t.name for t in TABLAS_DATOS_PRODUCTO if not inspector.has_table(t.name)]
        for tabla in TABLAS_DATOS_PRODUCTO:
            if inspector.has_table(tabla.name) and not set(tabla.c.keys()) <= {c['name'] for c in inspector.get_columns(tabla.name)}:
                raise ValueError('La ampliación existente tiene otro esquema; requiere revisión.')
        Producto.metadata.create_all(bind=conexion,tables=TABLAS_DATOS_PRODUCTO,checkfirst=True)
    preparar_ficha(engine)
    return 'Ficha completa preparada. Datos existentes conservados. Tablas nuevas: '+(', '.join(nuevas) or 'ninguna; ya estaba preparada')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--staging',action='store_true',required=True);parser.parse_args()
    if os.environ.get('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:
        raise SystemExit('Solo se permite preparar la ficha en laboratorio desconectado.')
    rama=os.environ.get('RENDER_GIT_BRANCH','')
    if rama and rama!='integracion-saas-2026-09': raise SystemExit('La rama del servicio no es integración.')
    servicio=os.environ.get('RENDER_EXTERNAL_URL','')
    if servicio and 'staging' not in servicio: raise SystemExit('El servicio no se identifica como staging.')
    url=os.environ.get('DATABASE_URL','')
    if not url: raise SystemExit('No se encontró la base del servicio.')
    if url.startswith('postgres://'): url='postgresql://'+url[len('postgres://'):]
    print(preparar(create_engine(url)))


if __name__=='__main__': main()
