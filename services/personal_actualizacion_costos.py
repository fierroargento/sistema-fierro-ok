"""Actualización idempotente de costos existentes al iniciar staging desconectado."""
from sqlalchemy import inspect
from models.fuentes_costo_productivo import EmpleadoProductivo, EmpleadoCostoVersion, RecursoEmpleadoProductivo
from services.personal_legajo import actualizar_horas_sueldo
from services.recursos_productivos import recalcular_tarifa_recurso
from services.seguridad_entorno import entorno_actual, laboratorio_forzado


def actualizar_costos_personal_al_iniciar(app, *, db):
    # La autorización actual es para UAT, incluso con bootstrap deshabilitado.
    # Salir antes de abrir una conexión fuera de staging desconectado.
    if entorno_actual() != 'staging' or not laboratorio_forzado():
        return {'estado':'fuera_de_alcance', 'empleados':0, 'recursos':0}
    with app.app_context():
        try:
            inspector = inspect(db.session.connection())
            tablas = [EmpleadoProductivo.__table__, EmpleadoCostoVersion.__table__, RecursoEmpleadoProductivo.__table__]
            if any(not inspector.has_table(t.name) or not set(t.c.keys()) <= {c['name'] for c in inspector.get_columns(t.name)} for t in tablas):
                db.session.rollback()
                app.logger.info('Personal: actualización de costos pendiente; esquema de costos no preparado.')
                return {'estado':'esquema_pendiente', 'empleados':0, 'recursos':0}
            # Orden estable y bloqueo de los maestros: dos workers no generan
            # versiones duplicadas. La segunda ejecución relee las tarifas.
            empleados = db.session.query(EmpleadoProductivo).filter_by(tipo_registro='empleado').order_by(EmpleadoProductivo.id).with_for_update().all()
            actualizados = []
            recursos_ids = set()
            for empleado in empleados:
                db.session.expire(empleado,['versiones_costo'])
                version = actualizar_horas_sueldo(empleado,
                    modelos={'EmpleadoCostoVersion':EmpleadoCostoVersion}, db_session=db.session,
                    usuario_id=None, usar_horas_existentes=True, recalcular_dependientes=False)
                if version is not None:
                    actualizados.append(empleado.id)
                    recursos_ids.update(v.recurso_id for v in empleado.participaciones_recurso)
            # Equipos compartidos se recalculan una sola vez, con todos los
            # integrantes ya actualizados, dentro de la misma transacción.
            recursos = db.session.query(EmpleadoProductivo).filter(EmpleadoProductivo.id.in_(recursos_ids)).order_by(EmpleadoProductivo.id).with_for_update().all() if recursos_ids else []
            for recurso in recursos:
                recalcular_tarifa_recurso(recurso,EmpleadoCostoVersion=EmpleadoCostoVersion,
                    db_session=db.session,usuario_id=None,commit=False)
            db.session.commit()
            resultado={'estado':'actualizado','empleados':len(actualizados),'recursos':len(recursos)}
            app.logger.info('Personal: costos actualizados automáticamente; empleados=%s, equipos=%s.',resultado['empleados'],resultado['recursos'])
            return resultado
        except Exception:
            db.session.rollback()
            # No servir tarifas parcialmente actualizadas. El error queda
            # visible en el deploy y la transacción anterior permanece íntegra.
            app.logger.exception('Personal: falló la actualización automática; se revirtieron todos los cambios.')
            raise
