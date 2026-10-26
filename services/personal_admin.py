"""Ficha administrativa sobre la identidad laboral existente, sin otra nómina."""
import hashlib
import json
from sqlalchemy import inspect
from services.fuentes_costo_productivo import crear_empleado

CAMPOS = {'codigo': 80, 'nombre': 200, 'sector': 120, 'puesto': 120, 'observacion': 500}


def datos_empleado(empleado):
    return {**{c: getattr(empleado, c) or '' for c in CAMPOS},
            'id': empleado.id, 'unidad_negocio_id': empleado.unidad_negocio_id,
            'activo': bool(empleado.activo)}


def huella_empleado(empleado, *, detalle=None, preparado=None):
    from models.personal_administrativo import PersonalDetalle
    from services.personal_legajo import datos_detalle
    from scripts.preparar_personal import preparado as esquema_preparado
    from extensions import db
    datos = datos_empleado(empleado)
    if preparado is None:
        preparado = esquema_preparado(db.session.get_bind())
        if preparado:
            detalle = db.session.get(PersonalDetalle, empleado.id)
    if preparado:
        datos['detalle'] = datos_detalle(detalle)
    return hashlib.sha256(json.dumps(datos, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def guardar_personal(formulario, *, organizacion_id, modelos, db_session):
    accion = formulario.get('accion')
    if accion not in {'crear', 'editar'}:
        raise ValueError('La acción de Personal no es válida.')
    datos = {}
    for campo, limite in CAMPOS.items():
        valor = str(formulario.get(campo) or '').strip()
        if campo in {'codigo', 'nombre', 'sector'} and not valor:
            raise ValueError(f'Completá {dict(codigo="el legajo", nombre="el nombre", sector="el sector")[campo]}.')
        if len(valor) > limite:
            raise ValueError(f'{campo.capitalize()}: el máximo es de {limite} caracteres.')
        datos[campo] = valor
    datos['codigo'] = datos['codigo'].lower()
    estado = formulario.get('activo')
    if estado not in {'0', '1'}:
        raise ValueError('Elegí Activo o Inactivo.')
    unidad_texto = str(formulario.get('unidad_negocio_id') or '').strip()
    if unidad_texto and not unidad_texto.isdecimal():
        raise ValueError('La unidad no es válida.')
    unidad_id = int(unidad_texto) if unidad_texto else None
    unidad = None
    if unidad_id is not None:
        unidad = db_session.query(modelos['UnidadNegocio']).filter_by(
            id=unidad_id, organizacion_id=organizacion_id).first()
        if unidad is None:
            raise ValueError('La unidad no pertenece a la organización.')
    Empleado = modelos['EmpleadoProductivo']
    if accion == 'crear':
        if unidad is not None and not unidad.activa:
            raise ValueError('Elegí una unidad activa para el alta.')
        empleado = crear_empleado(
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
            **datos, Organizacion=modelos['Organizacion'], UnidadNegocio=modelos['UnidadNegocio'],
            EmpleadoProductivo=Empleado, db_session=db_session, commit=False)
    else:
        ident = str(formulario.get('empleado_id') or '')
        if not ident.isdecimal():
            raise ValueError('El empleado no es válido.')
        empleado = db_session.query(Empleado).filter_by(
            id=int(ident), organizacion_id=organizacion_id,
            tipo_registro='empleado').with_for_update().first()
        if empleado is None:
            raise ValueError('El empleado no pertenece a la organización.')
        if formulario.get('huella') != huella_empleado(empleado):
            raise ValueError('La ficha cambió mientras la editabas. Cerrá y recargá Personal antes de volver a editar.')
        if datos['codigo'] != empleado.codigo.lower() or unidad_id != empleado.unidad_negocio_id:
            raise ValueError('El legajo y la unidad se conservan al editar una ficha existente.')
        if empleado.participaciones_recurso and datos['sector']!=empleado.sector:
            raise ValueError('El sector se modifica desde Áreas y tareas de la ficha.')
        if empleado.activo and estado == '0':
            Vinculo = modelos['RecursoEmpleadoProductivo']
            if not inspect(db_session.get_bind()).has_table(Vinculo.__tablename__):
                raise ValueError('No se pudo verificar la asignación a equipos. Conservá el empleado activo hasta revisar la configuración.')
            if db_session.query(Vinculo.id).filter_by(empleado_id=empleado.id).first():
                raise ValueError('El empleado integra un recurso productivo. Retiralo del equipo y recalculá su tarifa antes de desactivarlo.')
        for campo in ('nombre', 'sector', 'puesto', 'observacion'):
            setattr(empleado, campo, datos[campo] or None)
    empleado.activo = estado == '1'
    db_session.flush()
    if formulario.get('datos_ampliados_presentados') == '1':
        from services.personal_legajo import guardar_detalle
        guardar_detalle(empleado, formulario, db_session)
    return empleado
