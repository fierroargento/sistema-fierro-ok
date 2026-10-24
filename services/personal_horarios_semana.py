"""Edición conjunta de la semana, reutilizando registros y validación del legajo."""
import hashlib
import json
from models.personal_administrativo import HorarioPersonal
from services.personal_legajo import guardar_horario, actualizar_horas_sueldo, version_actual


def filas_semana(e, db_session):
    return [dict(id=str(h.id),dia_semana=str(h.dia_semana),entrada=h.entrada.strftime('%H:%M'),
        salida=h.salida.strftime('%H:%M'),nocturno='1' if h.nocturno else '0',
        pausa_minutos=str(h.pausa_minutos),desde=h.desde.isoformat(),hasta=h.hasta.isoformat() if h.hasta else '',
        observacion_horario=h.observacion or '') for h in db_session.query(HorarioPersonal).filter_by(
            empleado_id=e.id,estado='vigente').order_by(HorarioPersonal.dia_semana,HorarioPersonal.entrada,HorarioPersonal.id).all()]


def huella_semana(e, filas):
    return hashlib.sha256(json.dumps([e.organizacion_id,e.id,filas],sort_keys=True).encode()).hexdigest()


def leer_semana(texto):
    if not isinstance(texto,str) or len(texto)>60000:raise ValueError('Revisá los horarios de la semana.')
    try:filas=json.loads(texto)
    except (ValueError,TypeError) as error:raise ValueError('Revisá los horarios de la semana.') from error
    campos={'id','dia_semana','entrada','salida','nocturno','pausa_minutos','desde','hasta','observacion_horario'}
    if not isinstance(filas,list) or len(filas)>42 or any(not isinstance(f,dict) or set(f)!=campos or any(not isinstance(v,str) for v in f.values()) for f in filas):
        raise ValueError('Revisá la semana: máximo 42 franjas completas.')
    return filas


def guardar_semana(e, form, *, modelos, db_session, usuario_id):
    actuales=filas_semana(e,db_session)
    if form.get('huella')!=huella_semana(e,actuales):
        raise ValueError('Los horarios cambiaron mientras los editabas. Volvé a Horarios y recargá antes de guardar.')
    nuevas=leer_semana(form.get('semana'))
    if not nuevas and version_actual(e):raise ValueError('Cargá al menos un horario para calcular el costo del empleado.')
    anteriores={f['id']:f for f in actuales};ids=[f['id'] for f in nuevas if f['id']]
    if len(ids)!=len(set(ids)) or any(i not in anteriores for i in ids):raise ValueError('La semana contiene horarios ajenos o repetidos.')
    if any(f['dia_semana'] not in [str(i) for i in range(7)] or f['nocturno'] not in {'0','1'} for f in nuevas):raise ValueError('Revisá los días y la salida de cada horario.')
    conservar={f['id'] for f in nuevas if f['id'] and f==anteriores[f['id']]}
    cambiar=set(anteriores)-conservar
    for h in db_session.query(HorarioPersonal).filter(HorarioPersonal.empleado_id==e.id,HorarioPersonal.id.in_([int(i) for i in cambiar])).all():
        h.estado='cancelado'
    db_session.flush()
    for f in nuevas:
        if f['id'] not in conservar:guardar_horario(e,f,db_session)
    if cambiar or any(not f['id'] for f in nuevas):
        actualizar_horas_sueldo(e,modelos=modelos,db_session=db_session,usuario_id=usuario_id)
    return bool(cambiar or any(not f['id'] for f in nuevas))
