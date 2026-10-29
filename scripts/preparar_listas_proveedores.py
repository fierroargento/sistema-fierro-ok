"""Prepara tablas de cotizaciones, sin atribuir datos anteriores ni iniciar la app."""
from sqlalchemy import inspect
from models.listas_proveedores_compra import MaterialProveedorCompra,CotizacionProveedorCompra,ConfiguracionListaProveedor,CalculoCotizacionProveedor
TABLAS=(MaterialProveedorCompra.__table__,CotizacionProveedorCompra.__table__,ConfiguracionListaProveedor.__table__,CalculoCotizacionProveedor.__table__)

def preparado(conexion):
    from models.insumo_presentacion_compra import InsumoPresentacionCompra,InsumoPrecioBultoVersion
    i=inspect(conexion)
    tablas=(*TABLAS,InsumoPresentacionCompra.__table__,InsumoPrecioBultoVersion.__table__)
    return all(i.has_table(t.name) and set(t.c.keys())<={c['name'] for c in i.get_columns(t.name)} for t in tablas)

def preparar(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.compras import ProveedorCompra
    from models.fuentes_costo_productivo import InsumoProductivo,InsumoPrecioVersion
    with engine.begin() as c:
        i=inspect(c)
        for tabla in ['organizacion','unidad_negocio','proveedor_compra','insumo_productivo','insumo_precio_version']:
            if not i.has_table(tabla):raise ValueError('Falta preparar la base de Compras y materiales.')
        for t in TABLAS:
            if i.has_table(t.name) and not set(t.c.keys())<={c['name'] for c in i.get_columns(t.name)}:raise ValueError('El esquema de listas requiere revisión.')
            t.create(c,checkfirst=True)
    from scripts.preparar_bultos_insumos import preparar as preparar_bultos
    preparar_bultos(engine)
    return 'Listas de proveedores preparadas. Sin modificar materiales, productos, precios existentes ni movimientos.'

def main():
    import argparse,os
    from sqlalchemy import create_engine
    parser=argparse.ArgumentParser();parser.add_argument('--staging',action='store_true',required=True);parser.parse_args()
    if os.getenv('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:raise SystemExit('Se requiere laboratorio desconectado.')
    if os.getenv('RENDER_GIT_BRANCH','') not in {'','integracion-saas-2026-09'}:raise SystemExit('Se requiere la rama de integración.')
    if os.getenv('RENDER_EXTERNAL_URL','') and 'staging' not in os.getenv('RENDER_EXTERNAL_URL'):raise SystemExit('Se requiere staging.')
    url=os.getenv('DATABASE_URL','')
    if not url:raise SystemExit('No se encontró la base del servicio.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    engine=create_engine(url)
    try:print(preparar(engine))
    finally:engine.dispose()
if __name__=='__main__':main()
