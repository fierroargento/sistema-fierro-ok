"""Horas de costos derivadas del legajo, sin duplicar la jornada habitual."""
from datetime import date
from decimal import Decimal
from werkzeug.datastructures import MultiDict
from extensions import db
from models.fuentes_costo_productivo import EmpleadoCostoVersion, EmpleadoProductivo
from services.personal_legajo import horas_desde_horario, guardar_horario
from test_personal_admin import personal, entorno, campos, nuevo


def alta(**kw):
    return MultiDict(campos(cargar_sueldo_inicial='1', inicial_sueldo_base='1000',
        inicial_ubicacion_trabajo='Taller', inicial_tipo_funcion='directa', inicial_porcentaje_productivo='100',
        cargar_horario_inicial='1', inicial_dias=['0','1','2','3','4'], inicial_entrada='08:00',
        inicial_salida='17:00', inicial_pausa_minutos='60', inicial_desde='2020-01-01') | kw)


def test_alta_calcula_descansos_sin_horas_manuales_y_rechaza_manipulacion(personal):
    c,*_=personal
    assert c.post('/admin/personal', data=alta(inicial_horas_mensuales='9999')).status_code==302
    e=EmpleadoProductivo.query.one();v=EmpleadoCostoVersion.query.one()
    assert v.horas_mensuales==Decimal('173.33') and v.horas_productivas==v.horas_mensuales
    html=c.get(f'/admin/personal/{e.id}?seccion=sueldos').text
    assert 'Horas mensuales automáticas: 173.33' in html
    assert 'name="horas_mensuales"' not in html
    assert c.post(f'/admin/personal/{e.id}',data=dict(_csrf_token='csrf-personal',accion='guardar_sueldo',
        version_actual=v.id,sueldo_base='2000',ubicacion_trabajo='Taller',tipo_funcion='directa',
        porcentaje_productivo='100',horas_mensuales='9999')).status_code==302
    db.session.expire_all()
    assert [v for v in e.versiones_costo if v.vigente][0].horas_mensuales==Decimal('173.33')


def test_cambiar_horario_reversiona_tarifa_conservando_historia_y_jornada_completa(personal):
    c,*_=personal
    assert c.post('/admin/personal',data=alta(inicial_horas_productivas='100')).status_code==302
    e=EmpleadoProductivo.query.one();anterior=EmpleadoCostoVersion.query.one();tarifa=anterior.costo_hora_productiva_centavos
    r=c.post(f'/admin/personal/{e.id}',data=dict(_csrf_token='csrf-personal',accion='crear_horario',
        dia_semana='5',entrada='08:00',salida='12:00',pausa_minutos='0',desde='2020-01-01'))
    assert r.status_code==302,r.text
    db.session.expire_all();vigente=[v for v in e.versiones_costo if v.vigente][0]
    assert vigente.horas_mensuales==Decimal('190.67') and vigente.horas_productivas==vigente.horas_mensuales
    assert not anterior.vigente and anterior.costo_hora_productiva_centavos==tarifa
    assert vigente.costo_hora_productiva_centavos<tarifa


def test_calculo_nocturno_vigencias_y_cancelados(personal):
    e=nuevo(personal)
    h=guardar_horario(e,dict(dia_semana='6',entrada='22:00',salida='06:00',nocturno='1',pausa_minutos='30',desde='2026-01-01',hasta='2026-12-31'),db.session)
    assert horas_desde_horario(e,db.session,date(2026,10,23))==Decimal('32.50')
    assert horas_desde_horario(e,db.session,date(2027,1,1)) is None
    h.estado='cancelado';db.session.flush()
    assert horas_desde_horario(e,db.session,date(2026,10,23)) is None


def test_horario_invalido_no_deja_alta_ni_sueldo(personal):
    c,*_=personal
    assert c.post('/admin/personal',data=alta(inicial_pausa_minutos='540')).status_code==400
    assert EmpleadoProductivo.query.count()==0 and EmpleadoCostoVersion.query.count()==0
