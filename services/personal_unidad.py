"""Alcance del personal usando unidad primaria, áreas asignadas y vínculos explícitos."""
from sqlalchemy import or_,inspect
from models.personal_unidad import PersonalUnidad


def consulta(org,unidad,modelos,session):
    E=modelos['EmpleadoProductivo'];V=modelos['RecursoEmpleadoProductivo']
    condiciones=[E.unidad_negocio_id==unidad]
    i=inspect(session.connection())
    if i.has_table(V.__tablename__):
        R=E.__table__.alias('area_visible')
        ids=session.query(V.empleado_id).join(R,R.c.id==V.recurso_id).filter(R.c.organizacion_id==org,R.c.unidad_negocio_id==unidad,V.porcentaje_dedicacion>0)
        condiciones.append(E.id.in_(ids))
    if i.has_table(PersonalUnidad.__tablename__):
        condiciones.append(E.id.in_(session.query(PersonalUnidad.empleado_id).filter_by(organizacion_id=org,unidad_negocio_id=unidad)))
    return session.query(E).filter(E.organizacion_id==org,E.tipo_registro=='empleado',or_(*condiciones))


def unidades_del_empleado(e,modelos,session):
    ids={e.unidad_negocio_id} if e.unidad_negocio_id else set()
    ids.update(v.recurso.unidad_negocio_id for v in e.participaciones_recurso if v.recurso.organizacion_id==e.organizacion_id and v.porcentaje_dedicacion>0 and v.recurso.unidad_negocio_id)
    if inspect(session.connection()).has_table(PersonalUnidad.__tablename__):
        ids.update(v.unidad_negocio_id for v in session.query(PersonalUnidad).filter_by(organizacion_id=e.organizacion_id,empleado_id=e.id))
    return ids


def vincular(codigo,org,unidad,modelos,session):
    if not inspect(session.connection()).has_table(PersonalUnidad.__tablename__):raise ValueError('Falta preparar los vínculos de Personal por unidad.')
    E=modelos['EmpleadoProductivo'];U=modelos['UnidadNegocio']
    if session.query(U).filter_by(id=unidad,organizacion_id=org,activa=True).first() is None:raise ValueError('Unidad activa inválida.')
    e=session.query(E).filter_by(organizacion_id=org,tipo_registro='empleado',codigo=str(codigo or '').strip().lower()).with_for_update().first()
    if e is None:raise ValueError('No se encontró ese legajo en la empresa.')
    existente=session.query(PersonalUnidad).filter_by(empleado_id=e.id,unidad_negocio_id=unidad).first()
    if existente is None:session.add(PersonalUnidad(organizacion_id=org,empleado_id=e.id,unidad_negocio_id=unidad))
    session.flush();return e


def guardar_unidades(e, valores, *, modelos, session):
    """Reemplaza vínculos explícitos; mantiene áreas y costos existentes."""
    if not inspect(session.connection()).has_table(PersonalUnidad.__tablename__):
        raise ValueError('Falta preparar los vínculos de Personal por unidad.')
    if not valores or any(not str(v).isdecimal() for v in valores):
        raise ValueError('Seleccioná al menos una unidad de la empresa.')
    ids={int(v) for v in valores}
    propias={u.id for u in session.query(modelos['UnidadNegocio']).filter_by(organizacion_id=e.organizacion_id).all()}
    if not ids <= propias:
        raise ValueError('Una unidad seleccionada no pertenece a la empresa.')
    asignadas={v.recurso.unidad_negocio_id for v in e.participaciones_recurso if v.porcentaje_dedicacion>0}
    if not asignadas <= ids:
        raise ValueError('Antes de quitar una unidad, retirala del reparto en Áreas y tareas.')
    actuales=session.query(PersonalUnidad).filter_by(organizacion_id=e.organizacion_id,empleado_id=e.id).all()
    existentes={v.unidad_negocio_id for v in actuales}
    for v in actuales:
        if v.unidad_negocio_id not in ids:session.delete(v)
    for uid in sorted(ids-existentes):
        session.add(PersonalUnidad(organizacion_id=e.organizacion_id,empleado_id=e.id,unidad_negocio_id=uid))
    e.unidad_negocio_id=next(iter(ids)) if len(ids)==1 else None
    session.flush();session.expire(e,['unidad_negocio'])
    return ids
