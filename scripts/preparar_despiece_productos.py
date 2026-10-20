"""Despiece físico aditivo para el alta manual, exclusivamente staging."""
import argparse
import os
from sqlalchemy import create_engine,inspect


def preparar(engine):
    from models.organizacion import Organizacion
    from models.producto import Producto
    from models.unidad_negocio import UnidadNegocio
    from models.perfil_costeo_producto import PerfilCosteoProducto
    from models.producto_despiece_costeo import ProductoDespieceCosteo
    from scripts.preparar_datos_productos import preparar as preparar_datos
    preparar_datos(engine)
    with engine.begin() as c:
        i=inspect(c)
        if not all(i.has_table(t) for t in ('organizacion','producto','perfil_costeo_producto')):raise ValueError('Faltan las tablas base de Productos/Costos.')
        tabla=ProductoDespieceCosteo.__table__
        if i.has_table(tabla.name) and not set(tabla.c.keys())<={v['name'] for v in i.get_columns(tabla.name)}:raise ValueError('El despiece existente requiere revisión de esquema.')
        tabla.create(c,checkfirst=True)
    return 'Despiece de productos preparado. Datos existentes conservados.'


def main():
    p=argparse.ArgumentParser();p.add_argument('--staging',required=True,action='store_true');p.parse_args()
    if os.environ.get('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:raise SystemExit('Solo laboratorio desconectado.')
    if os.environ.get('RENDER_GIT_BRANCH','integracion-saas-2026-09')!='integracion-saas-2026-09':raise SystemExit('La rama no es integración.')
    if os.environ.get('RENDER_EXTERNAL_URL') and 'staging' not in os.environ['RENDER_EXTERNAL_URL']:raise SystemExit('El servicio no es staging.')
    url=os.environ.get('DATABASE_URL','')
    if not url:raise SystemExit('Falta DATABASE_URL.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    print(preparar(create_engine(url)))


if __name__=='__main__':main()
