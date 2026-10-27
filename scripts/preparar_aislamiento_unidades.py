"""Extensión explícita de Clientes y Personal para staging desconectado."""
import os,argparse
from sqlalchemy import create_engine
from scripts.preparar_clientes_unidad import preparar as preparar_clientes
from models.personal_unidad import PersonalUnidad


def preparar_personal(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.fuentes_costo_productivo import EmpleadoProductivo
    with engine.begin() as c:
        from sqlalchemy import inspect
        if not all(inspect(c).has_table(t) for t in ('organizacion','unidad_negocio','empleado_productivo')):raise ValueError('Falta el maestro de Personal.')
        PersonalUnidad.__table__.create(c,checkfirst=True)
    return 'Vínculos de Personal preparados. Sin reasignar legajos, sueldos ni áreas.'


def main():
    p=argparse.ArgumentParser();p.add_argument('--staging',action='store_true',required=True);p.parse_args()
    if os.getenv('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:raise SystemExit('Se requiere laboratorio desconectado.')
    if os.getenv('RENDER_GIT_BRANCH') and os.getenv('RENDER_GIT_BRANCH')!='integracion-saas-2026-09':raise SystemExit('Se requiere integración.')
    if os.getenv('RENDER_EXTERNAL_URL') and 'staging' not in os.getenv('RENDER_EXTERNAL_URL'):raise SystemExit('Se requiere staging.')
    url=os.getenv('DATABASE_URL','')
    if not url:raise SystemExit('Falta la base del servicio.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    e=create_engine(url)
    try:
        print(preparar_clientes(e));print(preparar_personal(e))
    finally:e.dispose()


if __name__=='__main__':main()
