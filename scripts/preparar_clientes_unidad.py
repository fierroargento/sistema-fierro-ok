"""Preparación explícita: no activa clientes ni contacta canales."""
from sqlalchemy import inspect,text
from models.cliente_unidad import ClienteUnidad


def preparado(conexion):
    i=inspect(conexion)
    return i.has_table('cliente_unidad') and all(i.has_table(t) and 'unidad_negocio_id' in {c['name'] for c in i.get_columns(t)} for t in ('actividad_crm','cliente_identidad_canal','lote_importacion_crm'))


def preparar(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.cliente_crm import ClienteCRM
    with engine.begin() as c:
        i=inspect(c)
        requeridas=('organizacion','unidad_negocio','cliente_crm','oportunidad_crm','actividad_crm','cliente_identidad_canal','lote_importacion_crm')
        if not all(i.has_table(t) for t in requeridas):raise ValueError('Faltan tablas base del CRM.')
        ClienteUnidad.__table__.create(c,checkfirst=True)
        for tabla in ('actividad_crm','cliente_identidad_canal','lote_importacion_crm'):
            if 'unidad_negocio_id' not in {x['name'] for x in i.get_columns(tabla)}:
                c.execute(text(f'ALTER TABLE {tabla} ADD COLUMN unidad_negocio_id INTEGER REFERENCES unidad_negocio(id)'))
            c.execute(text(f'CREATE INDEX IF NOT EXISTS ix_{tabla}_unidad_negocio_id ON {tabla}(unidad_negocio_id)'))
        # Sólo relaciones demostradas; sin adjudicar clientes generales a una unidad.
        c.execute(text('''INSERT INTO cliente_unidad (organizacion_id,cliente_id,unidad_negocio_id,activo)
          SELECT c.organizacion_id,c.id,c.unidad_negocio_id,c.activo FROM cliente_crm c
          JOIN unidad_negocio u ON u.id=c.unidad_negocio_id AND u.organizacion_id=c.organizacion_id
          WHERE NOT EXISTS(SELECT 1 FROM cliente_unidad v WHERE v.cliente_id=c.id AND v.unidad_negocio_id=c.unidad_negocio_id)'''))
        c.execute(text('''INSERT INTO cliente_unidad (organizacion_id,cliente_id,unidad_negocio_id,activo)
          SELECT DISTINCT o.organizacion_id,o.cliente_crm_id,o.unidad_negocio_id,c.activo FROM oportunidad_crm o
          JOIN cliente_crm c ON c.id=o.cliente_crm_id AND c.organizacion_id=o.organizacion_id
          JOIN unidad_negocio u ON u.id=o.unidad_negocio_id AND u.organizacion_id=o.organizacion_id
          WHERE NOT EXISTS(SELECT 1 FROM cliente_unidad v WHERE v.cliente_id=c.id AND v.unidad_negocio_id=o.unidad_negocio_id)'''))
        # Actividades con oportunidad tienen unidad verificable. El resto sólo si el cliente tenía unidad explícita.
        c.execute(text('''UPDATE actividad_crm SET unidad_negocio_id=(SELECT o.unidad_negocio_id FROM oportunidad_crm o WHERE o.id=actividad_crm.oportunidad_crm_id AND o.organizacion_id=actividad_crm.organizacion_id)
          WHERE unidad_negocio_id IS NULL AND oportunidad_crm_id IS NOT NULL'''))
        for tabla in ('actividad_crm','cliente_identidad_canal'):
            condicion=' AND oportunidad_crm_id IS NULL' if tabla=='actividad_crm' else ''
            c.execute(text(f'''UPDATE {tabla} SET unidad_negocio_id=(SELECT c.unidad_negocio_id FROM cliente_crm c WHERE c.id={tabla}.cliente_crm_id AND c.organizacion_id={tabla}.organizacion_id)
              WHERE unidad_negocio_id IS NULL{condicion}'''))
    return 'Clientes preparados por unidad. Registros generales sin evidencia conservados pendientes de asignación; lotes antiguos no se reasignan.'


def main():
    import argparse,os
    from sqlalchemy import create_engine
    parser=argparse.ArgumentParser();parser.add_argument('--staging',action='store_true',required=True);parser.parse_args()
    if os.getenv('MODO_LABORATORIO_DESCONECTADO','').lower() not in {'true','1','si'}:raise SystemExit('Se requiere laboratorio desconectado.')
    if os.getenv('RENDER_GIT_BRANCH') and os.getenv('RENDER_GIT_BRANCH')!='integracion-saas-2026-09':raise SystemExit('Se requiere integración.')
    if os.getenv('RENDER_EXTERNAL_URL') and 'staging' not in os.getenv('RENDER_EXTERNAL_URL'):raise SystemExit('Se requiere staging.')
    url=os.getenv('DATABASE_URL','')
    if not url:raise SystemExit('Falta la base del servicio.')
    if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
    engine=create_engine(url)
    try:print(preparar(engine))
    finally:engine.dispose()


if __name__=='__main__':main()
