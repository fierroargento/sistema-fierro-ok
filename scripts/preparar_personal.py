"""Preparación aditiva y acotada; nunca usa bootstrap ni modifica nóminas existentes."""
from sqlalchemy import inspect
from models.personal_administrativo import TABLAS_PERSONAL


def preparado(engine):
    inspector = inspect(engine)
    return all(inspector.has_table(t.name) and set(t.c.keys()) <= {c['name'] for c in inspector.get_columns(t.name)} for t in TABLAS_PERSONAL)


def preparar(engine):
    from models.fuentes_costo_productivo import EmpleadoProductivo
    with engine.begin() as conexion:
        inspector = inspect(conexion)
        if not all(inspector.has_table(t) for t in ('empleado_productivo','novedad_laboral_preparatoria','usuario_sistema','usuario_organizacion')):
            raise ValueError('Falta el maestro de empleados o de novedades laborales. No se preparó Personal.')
        for tabla in TABLAS_PERSONAL:
            if inspector.has_table(tabla.name) and not set(tabla.c.keys()) <= {c['name'] for c in inspector.get_columns(tabla.name)}:
                raise ValueError('El esquema de Personal necesita revisión. No se modificaron datos.')
        EmpleadoProductivo.metadata.create_all(bind=conexion, tables=TABLAS_PERSONAL, checkfirst=True)
    return 'Personal preparado. Los empleados, sueldos e historiales existentes se conservaron.'
