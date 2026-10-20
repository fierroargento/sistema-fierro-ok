"""Preparación aditiva e idempotente, solo en integración/staging desconectado."""
import argparse
import os
from sqlalchemy import create_engine, inspect


def preparar(engine):
    from models.organizacion import Organizacion
    from models.unidad_negocio import UnidadNegocio
    from models.cliente_crm import ClienteCRM
    from models.compras import ProveedorCompra
    from models.maestros_contacto import ClienteDomicilioFiscal, ProveedorContacto
    with engine.begin() as conexion:
        i = inspect(conexion)
        if not all(i.has_table(t) for t in ('organizacion', 'cliente_crm', 'proveedor_compra')):
            raise ValueError('Faltan las tablas base de clientes.')
        for modelo in (ClienteDomicilioFiscal, ProveedorContacto):
            tabla = modelo.__table__
            if i.has_table(tabla.name) and not set(tabla.c.keys()) <= {c['name'] for c in i.get_columns(tabla.name)}:
                raise ValueError('El esquema de contactos requiere revisión.')
        for modelo in (ClienteDomicilioFiscal, ProveedorContacto):
            modelo.__table__.create(conexion, checkfirst=True)
    return 'Domicilios de clientes y contactos de proveedores preparados. Datos existentes conservados.'


def main():
    p = argparse.ArgumentParser(); p.add_argument('--staging', action='store_true', required=True); p.parse_args()
    if os.environ.get('MODO_LABORATORIO_DESCONECTADO', '').lower() not in {'true', '1', 'si'}:
        raise SystemExit('Solo laboratorio desconectado.')
    if os.environ.get('RENDER_GIT_BRANCH') != 'integracion-saas-2026-09' or 'staging' not in os.environ.get('RENDER_EXTERNAL_URL', ''):
        raise SystemExit('Este comando requiere el servicio y la rama de staging.')
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        raise SystemExit('Falta DATABASE_URL.')
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    print(preparar(create_engine(url)))


if __name__ == '__main__':
    main()
