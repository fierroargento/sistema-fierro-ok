"""Corrección automática de legajos existentes al desplegar, sin bootstrap."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import pytest
from extensions import db
from models.fuentes_costo_productivo import EmpleadoProductivo, EmpleadoCostoVersion, RecursoEmpleadoProductivo
from services.fuentes_costo_productivo import registrar_costo_empleado, crear_empleado
from services.personal_legajo import guardar_horario
from services.personal_actualizacion_costos import actualizar_costos_personal_al_iniciar
from services.recursos_productivos import vincular_empleado, recalcular_tarifa_recurso
from test_personal_admin import personal, entorno, nuevo


def habilitar(monkeypatch):
    monkeypatch.setenv('SISTEMA_FIERRO_ENTORNO','staging')
    monkeypatch.setenv('MODO_LABORATORIO_DESCONECTADO','true')
    monkeypatch.setenv('BOOTSTRAP_BASE_DATOS_HABILITADO','false')


def sueldo(e,**kw):
    return registrar_costo_empleado(e,moneda='ARS',sueldo_base_centavos=100000,
        cargas_sociales_centavos=12345,horas_mensuales='160',horas_productivas='80',
        porcentaje_productivo='50',ubicacion_trabajo='Taller',tipo_funcion='directa',
        EmpleadoCostoVersion=EmpleadoCostoVersion,db_session=db.session,**kw)


def ejecutar(c):
    resultado=actualizar_costos_personal_al_iniciar(c.application,db=db)
    db.session.expire_all()
    return resultado


def test_arranque_actualiza_existentes_preserva_importes_e_historial_y_no_duplica(personal,monkeypatch):
    habilitar(monkeypatch);c,*_=personal;e=nuevo(personal)
    anterior=sueldo(e);anterior.porcentaje_cargas=Decimal('12.34');anterior.usa_porcentaje_general=True;db.session.commit()
    ident=anterior.id;tarifa=anterior.costo_hora_productiva_centavos
    guardar_horario(e,dict(dia_semana='0',entrada='08:00',salida='12:00',desde='2020-01-01'),db.session)
    guardar_horario(e,dict(dia_semana='0',entrada='16:00',salida='20:00',desde='2020-01-01'),db.session);db.session.commit()
    r=ejecutar(c);assert r==dict(estado='actualizado',empleados=1,recursos=0)
    actual=EmpleadoCostoVersion.query.filter_by(empleado_id=e.id,vigente=True).one()
    assert actual.id!=ident and actual.horas_mensuales==Decimal('34.67')
    assert actual.horas_productivas==actual.horas_mensuales and actual.porcentaje_productivo==100
    assert actual.sueldo_base_centavos==100000 and actual.cargas_sociales_centavos==12345
    assert actual.porcentaje_cargas==Decimal('12.34') and actual.usa_porcentaje_general
    assert actual.costo_mensual_total_centavos==112345
    viejo=db.session.get(EmpleadoCostoVersion,ident)
    assert not viejo.vigente and viejo.horas_productivas==80 and viejo.costo_hora_productiva_centavos==tarifa
    assert ejecutar(c)==dict(estado='actualizado',empleados=0,recursos=0)
    assert EmpleadoCostoVersion.query.count()==2


def test_sin_horario_usa_horas_existentes_y_no_crea_sueldos_faltantes(personal,monkeypatch):
    habilitar(monkeypatch);c,*_=personal;e=nuevo(personal);sueldo(e)
    nuevo(personal,codigo='sin-sueldo')
    assert ejecutar(c)['empleados']==1
    v=EmpleadoCostoVersion.query.filter_by(vigente=True).one()
    assert v.horas_mensuales==v.horas_productivas==160 and v.porcentaje_productivo==100
    assert EmpleadoCostoVersion.query.count()==2


def equipo(personal,empleados):
    c,org,_,u,m,*_=personal
    recurso=crear_empleado(organizacion_id=org.id,unidad_negocio_id=u.id,codigo='equipo-auto',nombre='Equipo',sector='Taller',
        Organizacion=m['Organizacion'],UnidadNegocio=m['UnidadNegocio'],EmpleadoProductivo=EmpleadoProductivo,db_session=db.session)
    recurso.tipo_registro='recurso';db.session.commit()
    for e in empleados:vincular_empleado(recurso,e,porcentaje_dedicacion=100,RecursoEmpleadoProductivo=RecursoEmpleadoProductivo,db_session=db.session)
    recalcular_tarifa_recurso(recurso,EmpleadoCostoVersion=EmpleadoCostoVersion,db_session=db.session)
    return recurso


def test_equipo_compartido_se_recalcula_una_vez_con_todos_los_integrantes(personal,monkeypatch):
    habilitar(monkeypatch);c,*_=personal
    uno=nuevo(personal);sueldo(uno);dos=nuevo(personal,codigo='dos');sueldo(dos)
    recurso=equipo(personal,[uno,dos]);cantidad=EmpleadoCostoVersion.query.count()
    assert ejecutar(c)==dict(estado='actualizado',empleados=2,recursos=1)
    assert EmpleadoCostoVersion.query.count()==cantidad+3
    v=EmpleadoCostoVersion.query.filter_by(empleado_id=recurso.id,vigente=True).one()
    assert v.horas_productivas==320 and v.costo_mensual_total_centavos==224690
    assert ejecutar(c)['recursos']==0


def test_error_en_equipo_revierte_todos_los_legajos_y_el_arranque_falla(personal,monkeypatch):
    import services.personal_actualizacion_costos as servicio
    habilitar(monkeypatch);c,*_=personal;e=nuevo(personal);sueldo(e);equipo(personal,[e])
    cantidad=EmpleadoCostoVersion.query.count()
    def falla(*a,**kw):raise ValueError('Fallo de prueba en equipo')
    monkeypatch.setattr(servicio,'recalcular_tarifa_recurso',falla)
    with pytest.raises(ValueError,match='Fallo de prueba'):
        ejecutar(c)
    db.session.expire_all()
    assert EmpleadoCostoVersion.query.count()==cantidad
    assert EmpleadoCostoVersion.query.filter_by(empleado_id=e.id,vigente=True).one().horas_productivas==80


@pytest.mark.parametrize('entorno,lab',[('produccion','true'),('staging','false'),('desarrollo','true')])
def test_fuera_de_staging_desconectado_no_abre_conexion(monkeypatch,entorno,lab):
    monkeypatch.setenv('SISTEMA_FIERRO_ENTORNO',entorno);monkeypatch.setenv('MODO_LABORATORIO_DESCONECTADO',lab)
    assert actualizar_costos_personal_al_iniciar(None,db=None)['estado']=='fuera_de_alcance'


def test_sin_esquema_no_crea_tablas(personal,monkeypatch):
    from sqlalchemy import inspect
    habilitar(monkeypatch);c,*_=personal
    db.metadata.drop_all(db.engine,tables=[RecursoEmpleadoProductivo.__table__])
    assert ejecutar(c)['estado']=='esquema_pendiente'
    assert not inspect(db.engine).has_table(RecursoEmpleadoProductivo.__tablename__)


def test_app_invoca_actualizacion_automatica_fuera_del_bootstrap():
    fuente=Path('app.py').read_text()
    assert 'actualizar_costos_personal_al_iniciar(app, db=db)' in fuente
    assert fuente.index('actualizar_costos_personal_al_iniciar(app, db=db)')>fuente.index('inicializar_base_datos_saas(\n    app,')
