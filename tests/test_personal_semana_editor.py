import json
import pytest
from extensions import db
from models.personal_administrativo import HorarioPersonal
from models.fuentes_costo_productivo import EmpleadoCostoVersion
from services.personal_legajo import guardar_horario
from services.personal_horarios_semana import filas_semana,huella_semana
from test_personal_admin import personal,entorno,nuevo
from test_personal_actualizacion_costos import sueldo


def post(e,filas=None,**kw):
    actuales=filas_semana(e,db.session)
    return dict(_csrf_token='csrf-personal',semana=json.dumps(actuales if filas is None else filas),huella=huella_semana(e,actuales))|kw


def fila(dia=0,entrada='08:00',salida='12:00'):
    return dict(id='',dia_semana=str(dia),entrada=entrada,salida=salida,nocturno='0',pausa_minutos='0',desde='2020-01-01',hasta='',observacion_horario='')


def url(e,editar=True):return f'/admin/personal/{e.id}/horarios'+('?modo=editar' if editar else '')


def test_ver_y_gestionar_abren_semana_precargada_y_get_no_escribe(personal):
    c,*_=personal;e=nuevo(personal);guardar_horario(e,fila(),db.session);db.session.commit()
    ficha=c.get(f'/admin/personal/{e.id}?seccion=horarios').text
    assert 'data-personal-abrir="personal-horario"' not in ficha and '>Gestionar</a>' in ficha and '>Ver</a>' in ficha
    assert 'Cancelar horario</button>' not in ficha
    for editar in [False,True]:
        r=c.get(url(e,editar));assert r.status_code==200 and '08:00' in r.text and 'semana-form' in r.text
        assert ('Guardar horario semanal</button>' in r.text)==editar
    assert HorarioPersonal.query.count()==1


def test_semana_edita_y_agrega_corte_atomicamente_y_recalcula_costo(personal):
    c,*_=personal;e=nuevo(personal);sueldo(e)
    viejo=guardar_horario(e,fila(),db.session);db.session.commit()
    filas=filas_semana(e,db.session);filas[0]['salida']='13:00';filas += [fila(0,'16:00','20:00'),fila(1,'09:00','14:00')]
    assert c.post(url(e),data=post(e,filas)).status_code==302
    db.session.expire_all();assert viejo.estado=='cancelado'
    assert HorarioPersonal.query.filter_by(estado='vigente').count()==3
    assert HorarioPersonal.query.count()==4
    v=EmpleadoCostoVersion.query.filter_by(empleado_id=e.id,vigente=True).one()
    assert float(v.horas_productivas)==60.67 and v.horas_productivas==v.horas_mensuales
    assert c.post(url(e),data=post(e)).status_code==302
    assert HorarioPersonal.query.count()==4 and EmpleadoCostoVersion.query.count()==2


def test_error_superposicion_restaura_edicion_sin_cancelar_lo_anterior(personal):
    c,*_=personal;e=nuevo(personal);h=guardar_horario(e,fila(),db.session);db.session.commit()
    filas=filas_semana(e,db.session);filas[0]['salida']='15:00';filas.append(fila(0,'14:00','18:00'))
    r=c.post(url(e),data=post(e,filas));assert r.status_code==400 and 'superpone' in r.text and '18:00' in r.text
    db.session.expire_all();assert h.estado=='vigente' and h.salida.hour==12 and HorarioPersonal.query.count()==1


def test_semana_obsoleta_y_registros_ajenos_no_modifican_datos(personal):
    c,*_=personal;e=nuevo(personal);f=post(e,[fila()])
    guardar_horario(e,fila(1),db.session);db.session.commit()
    assert c.post(url(e),data=f).status_code==400
    assert c.post(url(e),data=post(e,[dict(fila(),id='99999')])).status_code==400
    assert HorarioPersonal.query.count()==1


def test_edicion_protegida_por_tenant_csrf_y_modo_lectura(personal):
    c,org,otra,u,m,mem=personal;e=nuevo(personal)
    assert c.post(url(e),data={}).status_code==400
    assert c.post(url(e,False),data=post(e)).status_code==405
    assert c.get('/admin/personal/999999/horarios').status_code==404
    e.organizacion_id=otra.id;db.session.commit();assert c.get(url(e)).status_code==404
    e.organizacion_id=org.id;db.session.commit();mem.rol='carga'
    assert c.post(url(e),data=post(e,[fila()])).status_code==302
    assert HorarioPersonal.query.count()==0


def test_se_puede_quitar_un_dia_y_dejar_otro_sin_perder_historial(personal):
    c,*_=personal;e=nuevo(personal)
    for dia in [0,1]:guardar_horario(e,fila(dia),db.session)
    db.session.commit();filas=filas_semana(e,db.session)[1:]
    assert c.post(url(e),data=post(e,filas)).status_code==302
    assert HorarioPersonal.query.count()==2 and HorarioPersonal.query.filter_by(estado='vigente').count()==1
