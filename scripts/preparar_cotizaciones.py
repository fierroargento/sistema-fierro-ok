"""Preparación aditiva de cotización general y desgaste común; sin cargar valores."""
from sqlalchemy import inspect
from models.cotizaciones import CotizacionDolar,DesgasteLaserVersion
TABLAS=(CotizacionDolar.__table__,DesgasteLaserVersion.__table__)

def preparado(conexion):
    i=inspect(conexion)
    return all(i.has_table(t.name) and set(t.c.keys())<={c['name'] for c in i.get_columns(t.name)} for t in TABLAS)

def preparar(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.fuentes_costo_productivo import MaquinaProductiva
    with engine.begin() as c:
        i=inspect(c)
        if not all(i.has_table(n) for n in ['organizacion','unidad_negocio','maquina_productiva']):raise ValueError('Falta la base de empresa, unidades y máquinas.')
        for t in TABLAS:
            if i.has_table(t.name) and not set(t.c.keys())<={col['name'] for col in i.get_columns(t.name)}:raise ValueError('Esquema de cotizaciones incompatible; requiere revisión.')
            t.create(c,checkfirst=True)
    return 'Cotizaciones preparadas. Sin dólar predeterminado, máquinas ni precios cargados.'

def main():
    import argparse,os
    from sqlalchemy import create_engine
    p=argparse.ArgumentParser();p.add_argument('--staging',action='store_true',required=True);p.parse_args()
    if os.getenv('MODO_LABORATORIO_DESCONECTADO','').lower() not in ('true','1','si') or os.getenv('RENDER_GIT_BRANCH')!='integracion-saas-2026-09' or 'staging' not in os.getenv('RENDER_EXTERNAL_URL','').lower():raise SystemExit('Se requiere staging de integración con laboratorio desconectado.')
    url=os.getenv('DATABASE_URL','')
    if not url:raise SystemExit('Falta la base del servicio.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    e=create_engine(url)
    try:print(preparar(e))
    finally:e.dispose()
if __name__=='__main__':main()
