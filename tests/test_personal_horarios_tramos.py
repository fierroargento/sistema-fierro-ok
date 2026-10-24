"""Días distintos y jornadas cortadas: misma fuente de horarios y costo."""
import json
from decimal import Decimal
import pytest
from extensions import db
from models.personal_administrativo import HorarioPersonal
from models.fuentes_costo_productivo import EmpleadoProductivo, EmpleadoCostoVersion
from test_personal_admin import personal, entorno, campos


def tramo(dia, entrada, salida, pausa='0', nocturno='0'):
    return dict(dia_semana=str(dia),entrada=entrada,salida=salida,pausa_minutos=pausa,nocturno=nocturno)


def alta(tramos,**kw):
    return campos(cargar_horario_inicial='1',inicial_tramos=json.dumps(tramos),
        inicial_desde='2020-01-01',cargar_sueldo_inicial='1',inicial_sueldo_base='1000',
        inicial_ubicacion_trabajo='Taller',inicial_tipo_funcion='directa')|kw


def test_horarios_distintos_y_cortados_suman_solo_tramos_netos(personal):
    c,*_=personal
    tramos=[tramo(0,'08:00','12:00'),tramo(0,'16:00','20:00'),tramo(1,'09:00','15:00','30')]
    assert c.post('/admin/personal',data=alta(tramos,inicial_horas_productivas='1',inicial_porcentaje_productivo='5')).status_code==302
    assert HorarioPersonal.query.count()==3
    v=EmpleadoCostoVersion.query.one()
    assert v.horas_mensuales==Decimal('58.50') and v.horas_productivas==v.horas_mensuales
    assert v.porcentaje_productivo==100
    e=EmpleadoProductivo.query.one()
    html=c.get(f'/admin/personal/{e.id}?seccion=horarios').text
    assert '08:00 / 12:00' in html and '16:00 / 20:00' in html and '09:00 / 15:00' in html
    sueldo=c.get(f'/admin/personal/{e.id}?seccion=sueldos').text
    assert 'name="horas_productivas"' not in sueldo and 'name="porcentaje_productivo"' not in sueldo


@pytest.mark.parametrize('tramos',[
    [],[tramo(0,'08:00','12:00'),tramo(0,'11:00','15:00')],
    [tramo(6,'22:00','06:00',nocturno='1'),tramo(0,'05:00','08:00')],
    [tramo(7,'08:00','12:00')],[tramo(0,'08:00','12:00','240')],
    [tramo(0,'08:00','12:00')]*43,[{'dia_semana':'0'}],{'dia_semana':'0'},
    [dict(tramo(0,'08:00','12:00'),entrada=None)]
])
def test_tramos_invalidos_revierten_toda_la_carga(personal,tramos):
    c,*_=personal
    r=c.post('/admin/personal',data=alta(tramos))
    assert r.status_code==400
    assert EmpleadoProductivo.query.count()==0 and HorarioPersonal.query.count()==0 and EmpleadoCostoVersion.query.count()==0


def test_limites_contiguos_y_nocturno_se_guardan_sin_contar_corte(personal):
    c,*_=personal
    assert c.post('/admin/personal',data=alta([tramo(0,'08:00','12:00'),tramo(0,'12:00','14:00'),tramo(6,'22:00','06:00','30','1')])).status_code==302
    v=EmpleadoCostoVersion.query.one();assert v.horas_productivas==Decimal('58.50')


def test_error_conserva_horario_ingresado_y_no_secretos(personal):
    c,*_=personal
    tramos=[tramo(0,'08:00','12:00'),tramo(0,'16:00','20:00')]
    f=alta(tramos,inicial_sueldo_base='monto-invalido',password='secreto-ficticio')
    r=c.post('/admin/personal',data=f)
    assert r.status_code==400 and 'inicial_tramos' in r.text
    assert '16:00' in r.text and 'secreto-ficticio' not in r.text
    assert HorarioPersonal.query.count()==0
