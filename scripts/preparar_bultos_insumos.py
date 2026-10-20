"""Preparación aditiva de presentaciones de compra, solo staging."""
import argparse
import os
from sqlalchemy import create_engine, inspect


def preparar(engine):
    from models.organizacion import Organizacion
    from models.fuentes_costo_productivo import InsumoProductivo
    from models.insumo_presentacion_compra import InsumoPresentacionCompra, InsumoPrecioBultoVersion
    with engine.begin() as conexion:
        i = inspect(conexion)
        if not all(i.has_table(t) for t in ('organizacion', 'insumo_productivo', 'insumo_precio_version')):
            raise ValueError('Faltan las tablas base de insumos.')
        for Modelo in (InsumoPresentacionCompra, InsumoPrecioBultoVersion):
            if i.has_table(Modelo.__tablename__) and not set(Modelo.__table__.c.keys()) <= {c['name'] for c in i.get_columns(Modelo.__tablename__)}:
                raise ValueError('El esquema de presentaciones requiere revisión.')
        for Modelo in (InsumoPresentacionCompra, InsumoPrecioBultoVersion):
            Modelo.__table__.create(conexion, checkfirst=True)
    return 'Bultos de insumos preparados. Insumos y precios existentes conservados.'


def main():
    p = argparse.ArgumentParser(); p.add_argument('--staging', required=True, action='store_true'); p.parse_args()
    if os.environ.get('MODO_LABORATORIO_DESCONECTADO', '').lower() not in {'true', '1', 'si'}:
        raise SystemExit('Solo laboratorio desconectado.')
    if os.environ.get('RENDER_GIT_BRANCH', 'integracion-saas-2026-09') != 'integracion-saas-2026-09':
        raise SystemExit('La rama no es integración.')
    if os.environ.get('RENDER_EXTERNAL_URL') and 'staging' not in os.environ['RENDER_EXTERNAL_URL']:
        raise SystemExit('El servicio no es staging.')
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        raise SystemExit('Falta DATABASE_URL.')
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    print(preparar(create_engine(url)))


if __name__ == '__main__':
    main()
