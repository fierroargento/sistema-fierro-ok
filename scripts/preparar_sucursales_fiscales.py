"""Migración explícita y aditiva: no activa CUIT, sucursales ni emisión."""
from sqlalchemy import inspect
from models.sucursal_fiscal import TABLAS_SUCURSAL_FISCAL


def preparado(engine):
    inspector = inspect(engine)
    return all(inspector.has_table(t.name) and set(t.c.keys()) <=
               {c['name'] for c in inspector.get_columns(t.name)} for t in TABLAS_SUCURSAL_FISCAL)


def preparar(engine):
    # Registrar las tablas referenciadas sin importar app.py ni ejecutar bootstrap.
    from models.organizacion import Organizacion
    from models.sucursal_operativa import SucursalOperativa
    from models.entidad_fiscal import EntidadFiscal
    from models.punto_venta_fiscal import PuntoVentaFiscal
    from models.borrador_comprobante_fiscal import BorradorComprobanteFiscal
    with engine.begin() as conexion:
        inspector = inspect(conexion)
        for nombre in ('organizacion', 'sucursal_operativa', 'entidad_fiscal', 'punto_venta_fiscal', 'borrador_comprobante_fiscal'):
            if not inspector.has_table(nombre):
                raise ValueError('Falta la estructura fiscal existente; no se prepararon sucursales fiscales.')
        for tabla in TABLAS_SUCURSAL_FISCAL:
            if inspector.has_table(tabla.name) and not set(tabla.c.keys()) <= {c['name'] for c in inspector.get_columns(tabla.name)}:
                raise ValueError('El esquema fiscal necesita revisión.')
        TABLAS_SUCURSAL_FISCAL[0].metadata.create_all(conexion, tables=TABLAS_SUCURSAL_FISCAL, checkfirst=True)
    return 'Sucursales fiscales preparadas. Sin asignaciones automáticas ni emisión real.'


def main():
    import argparse
    import os
    from sqlalchemy import create_engine
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", action="store_true", required=True)
    parser.parse_args()
    if os.environ.get("MODO_LABORATORIO_DESCONECTADO", "").lower() not in {"true", "1", "si"}:
        raise SystemExit("Solo se permite preparar sucursales fiscales en laboratorio desconectado.")
    rama = os.environ.get("RENDER_GIT_BRANCH", "")
    if rama and rama != "integracion-saas-2026-09":
        raise SystemExit("La rama del servicio no es la de integración.")
    servicio = os.environ.get("RENDER_EXTERNAL_URL", "")
    if servicio and "staging" not in servicio:
        raise SystemExit("El servicio no se identifica como staging.")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("No se encontró la base del servicio.")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    engine = create_engine(url)
    try:
        print(preparar(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
