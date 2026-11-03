"""Preparación aditiva, sin importes ni repartos predeterminados."""
from sqlalchemy import inspect
from models.reparto_gasto_sector import RepartoGastoSector

def preparar(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.fuentes_costo_productivo import CostoFijoProductivo
    with engine.begin() as c:
        i=inspect(c)
        if not all(i.has_table(n) for n in ['organizacion','costo_fijo_productivo']):raise ValueError('Falta la base de gastos.')
        t=RepartoGastoSector.__table__
        if i.has_table(t.name) and not set(t.c.keys())<={x['name'] for x in i.get_columns(t.name)}:raise ValueError('Esquema incompatible.')
        t.create(c,checkfirst=True)
    return 'Reparto por sectores preparado. Sin gastos, obligaciones, pagos ni repartos cargados.'

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
