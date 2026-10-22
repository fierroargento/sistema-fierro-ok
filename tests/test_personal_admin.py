"""Integración aislada: Personal comparte identidad y costos laborales existentes."""
import ast
import hmac
from pathlib import Path
from types import SimpleNamespace
import pytest
from flask import request, session, abort
from extensions import db
from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio
from models.usuario_sistema import UsuarioSistema
from models.usuario_organizacion import UsuarioOrganizacion
from models.fuentes_costo_productivo import EmpleadoProductivo, EmpleadoCostoVersion, RecursoEmpleadoProductivo, ConfiguracionCostoLaboralVersion, EmpleadoDistribucionVersion
from services.personal_admin import datos_empleado, huella_empleado
from services.fuentes_costo_productivo import crear_empleado, registrar_costo_empleado
from services.recursos_productivos import vincular_empleado, configurar_integrantes
from test_producto_ficha_maestra import entorno


@pytest.fixture()
def personal(entorno, monkeypatch):
    from modules.admin.personal import routes
    app, org, otra, unidad = entorno
    db.metadata.create_all(db.engine, tables=[UsuarioSistema.__table__, EmpleadoProductivo.__table__, EmpleadoCostoVersion.__table__, RecursoEmpleadoProductivo.__table__])
    from models.personas import TurnoLaboralPlanificado, NovedadLaboralPreparatoria, CompetenciaEmpleadoPreparatoria
    from scripts.preparar_personal import preparar
    from models.personal_administrativo import TABLAS_PERSONAL
    db.metadata.create_all(db.engine,tables=[UsuarioOrganizacion.__table__,ConfiguracionCostoLaboralVersion.__table__, EmpleadoDistribucionVersion.__table__,TurnoLaboralPlanificado.__table__,NovedadLaboralPreparatoria.__table__,CompetenciaEmpleadoPreparatoria.__table__])
    preparar(db.engine)
    modelos = dict(UsuarioSistema=UsuarioSistema,UsuarioOrganizacion=UsuarioOrganizacion,Organizacion=Organizacion, UnidadNegocio=UnidadNegocio, EmpleadoProductivo=EmpleadoProductivo, RecursoEmpleadoProductivo=RecursoEmpleadoProductivo,
        ConfiguracionCostoLaboralVersion=ConfiguracionCostoLaboralVersion,EmpleadoCostoVersion=EmpleadoCostoVersion,
        EmpleadoDistribucionVersion=EmpleadoDistribucionVersion,TurnoLaboralPlanificado=TurnoLaboralPlanificado,
        NovedadLaboralPreparatoria=NovedadLaboralPreparatoria,CompetenciaEmpleadoPreparatoria=CompetenciaEmpleadoPreparatoria)
    mem = SimpleNamespace(rol='admin', organizacion_id=org.id, organizacion=org)
    monkeypatch.setattr(routes, 'resolver_tenant_usuario', lambda *a, **k: mem)
    app.register_blueprint(routes.crear_blueprint_personal(dependencias=dict(db=db, modelos=modelos,
        usuario_actual=lambda: SimpleNamespace(id=1), UsuarioOrganizacion=UsuarioOrganizacion,
        login_required=lambda f: f, registrar_auditoria=lambda *a, **k: None)))
    app.add_url_rule('/', endpoint='inicio', view_func=lambda:'Inicio')
    app.add_url_rule('/admin/comercial/fuentes-costos', endpoint='admin_comercial.fuentes_costos', view_func=lambda:'Costos')
    app.url_build_error_handlers.append(lambda e, endpoint, values: '/sin-uso/'+endpoint)
    app.jinja_env.globals.update(puede_crear_pedido=lambda:False, puede_ver_historico=lambda:False, alertas_operativas=lambda:[])
    app.context_processor(lambda:dict(rol_actual=mem.rol, usuario_logueado=SimpleNamespace(id=1,nombre="Admin de prueba",username="admin-test"), csrf_token_value='csrf-personal',csp_nonce='test'))
    # Ejecutar el guardián global real sin importar app.py ni iniciar conexiones/scheduler.
    fuente=ast.parse(Path('app.py').read_text())
    funcion=next(n for n in fuente.body if isinstance(n,ast.FunctionDef) and n.name=='validar_csrf')
    funcion.decorator_list=[]
    espacio=dict(app=app, request=request, session=session, abort=abort, hmac=hmac)
    exec(compile(ast.Module(body=[funcion], type_ignores=[]),'csrf-real','exec'),espacio)
    app.before_request(espacio['validar_csrf']);app.config['TESTING']=False
    c=app.test_client()
    with c.session_transaction() as s:s['_csrf_token']='csrf-personal';s['unidad_negocio_id']=unidad.id
    yield c, org, otra, unidad, modelos, mem
    db.session.rollback()
    db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS_PERSONAL))+[TurnoLaboralPlanificado.__table__,NovedadLaboralPreparatoria.__table__,CompetenciaEmpleadoPreparatoria.__table__,EmpleadoDistribucionVersion.__table__,ConfiguracionCostoLaboralVersion.__table__,RecursoEmpleadoProductivo.__table__, EmpleadoCostoVersion.__table__, EmpleadoProductivo.__table__,UsuarioOrganizacion.__table__,UsuarioSistema.__table__])


def campos(**cambios):
    return dict(accion='crear',codigo='LEG-001',nombre='Persona ficticia',sector='Taller',puesto='Armador',observacion='Prueba',unidad_negocio_id='',activo='1',_csrf_token='csrf-personal') | cambios


def nuevo(p, **cambios):
    c,org,_,unidad,*_=p
    r=c.post('/admin/personal',data=campos(unidad_negocio_id=str(unidad.id),**cambios))
    assert r.status_code==302,r.text
    return EmpleadoProductivo.query.filter_by(organizacion_id=org.id,codigo=cambios.get('codigo','leg-001').lower()).one()


def editar(e, **cambios):
    return campos(accion='editar',empleado_id=str(e.id),huella=huella_empleado(e),
        codigo=e.codigo,nombre=e.nombre,sector=e.sector,puesto=e.puesto or '',observacion=e.observacion or '',
        unidad_negocio_id=str(e.unidad_negocio_id or ''),activo='1' if e.activo else '0') | cambios


def test_alta_administrativa_sin_sueldo_y_unica_identidad(personal):
    c,org,_,u,*_=personal;e=nuevo(personal)
    assert e.tipo_registro=='empleado' and e.unidad_negocio_id==u.id
    assert EmpleadoCostoVersion.query.count()==0
    r=c.get('/admin/personal');assert r.status_code==200
    assert 'leg-001' in r.text and 'Administración / Personal' in r.text
    assert 'admin_personal.js' in r.text and 'data-personal-editar' in r.text
    assert 'name="sueldo_base"' not in r.text
    r=c.post('/admin/personal',data=campos(codigo='LEG-001'))
    assert r.status_code==400 and EmpleadoProductivo.query.count()==1


def test_costo_posterior_y_edicion_conservan_id_tarifa_e_historial(personal):
    c,org,_,_,*_=personal;e=nuevo(personal)
    registrar_costo_empleado(e,moneda='ARS',sueldo_base_centavos=100000,
        horas_mensuales='100',horas_productivas='80',EmpleadoCostoVersion=EmpleadoCostoVersion,db_session=db.session)
    ident=e.id;version=EmpleadoCostoVersion.query.one();tarifa=version.costo_hora_productiva_centavos
    r=c.post('/admin/personal',data=editar(e,nombre='Nuevo nombre',sector='Administración'))
    assert r.status_code==302
    db.session.expire_all();assert db.session.get(EmpleadoProductivo,ident).nombre=='Nuevo nombre'
    assert EmpleadoCostoVersion.query.count()==1 and version.costo_hora_productiva_centavos==tarifa
    assert version.empleado_id==ident


def test_aislamiento_tenant_recursos_y_unidades(personal):
    c,org,otra,u,m,_=personal
    ua=UnidadNegocio(organizacion_id=otra.id,codigo='otra',nombre='Ajena');db.session.add(ua);db.session.commit()
    ajeno=crear_empleado(organizacion_id=otra.id,unidad_negocio_id=ua.id,codigo='AJENO',nombre='Ajeno',sector='Otro',Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,EmpleadoProductivo=EmpleadoProductivo,db_session=db.session)
    e=nuevo(personal)
    recurso=crear_empleado(organizacion_id=org.id,unidad_negocio_id=u.id,codigo='EQUIPO',nombre='Equipo',sector='Taller',Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,EmpleadoProductivo=EmpleadoProductivo,db_session=db.session)
    recurso.tipo_registro='recurso';db.session.commit()
    for registro in [ajeno,recurso]:
        assert c.post('/admin/personal',data=editar(registro,nombre='Alterado')).status_code==400
    assert c.post('/admin/personal',data=campos(codigo='OTRO',unidad_negocio_id=str(ua.id))).status_code==400
    r=c.get('/admin/personal');assert 'AJENO' not in r.text and 'data-personal-editar="'+str(recurso.id)+'"' not in r.text
    assert c.post('/admin/personal/costos',data=dict(_csrf_token='csrf-personal',empleado_id=ajeno.id)).location.startswith('/admin/personal?error=')
    assert c.post('/admin/personal',data=editar(e,unidad_negocio_id='')).status_code==400


def test_concurrencia_y_cancelacion_no_escriben(personal):
    c,*_=personal;e=nuevo(personal);antes=editar(e)
    assert c.post('/admin/personal',data=editar(e,nombre='Primera edición')).status_code==302
    assert c.post('/admin/personal',data=antes|{'nombre':'Edición antigua'}).status_code==400
    db.session.expire_all();assert e.nombre=='Primera edición'
    # Consultar la pantalla/ver fichas no altera datos ni tarifas.
    for _ in range(2):assert c.get('/admin/personal').status_code==200
    assert EmpleadoProductivo.query.count()==1 and EmpleadoCostoVersion.query.count()==0


@pytest.mark.parametrize('cambio', [dict(nombre=''),dict(sector=''),dict(puesto='x'*121),dict(observacion='x'*501),dict(activo='otro'),dict(unidad_negocio_id='-1')])
def test_error_atomico_conserva_formulario(personal,cambio):
    c,*_=personal
    r=c.post('/admin/personal',data=campos(**cambio))
    assert r.status_code==400 and EmpleadoProductivo.query.count()==0
    assert '"formulario_error": {' in r.text


def test_inactivo_no_entra_en_equipos_y_baja_asignada_se_bloquea(personal):
    c,org,_,u,*_=personal;e=nuevo(personal)
    recurso=crear_empleado(organizacion_id=org.id,unidad_negocio_id=u.id,codigo='equipo',nombre='Equipo',sector='Taller',Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,EmpleadoProductivo=EmpleadoProductivo,db_session=db.session)
    recurso.tipo_registro='recurso';db.session.commit()
    vincular_empleado(recurso,e,porcentaje_dedicacion=100,RecursoEmpleadoProductivo=RecursoEmpleadoProductivo,db_session=db.session)
    assert c.post('/admin/personal',data=editar(e,activo='0')).status_code==400
    assert e.activo
    db.session.delete(RecursoEmpleadoProductivo.query.one());db.session.commit()
    assert c.post('/admin/personal',data=editar(e,activo='0')).status_code==302
    for fn,args in [(vincular_empleado,(recurso,e)),(configurar_integrantes,(recurso,[(e,100)]))]:
        with pytest.raises(ValueError,match='inactivo'):fn(*args,RecursoEmpleadoProductivo=RecursoEmpleadoProductivo,db_session=db.session)
    assert RecursoEmpleadoProductivo.query.count()==0


def test_csrf_roles_busqueda_y_contexto_de_costo(personal):
    c,org,_,u,_,mem=personal;e=nuevo(personal)
    assert c.post('/admin/personal',data=campos(codigo='NUEVO',_csrf_token='')).status_code==400
    assert c.post('/admin/personal/costos',data={'empleado_id':e.id}).status_code==400
    r=c.post('/admin/personal/costos',data={'empleado_id':e.id,'_csrf_token':'csrf-personal'})
    assert r.status_code==302 and r.location.endswith('/admin/personal/'+str(e.id)+'?seccion=sueldos')
    with c.session_transaction() as s:assert s['unidad_negocio_id']==u.id
    assert 'Persona ficticia' in c.get('/admin/personal?buscar=ficticia').text
    assert 'data-personal-editar' not in c.get('/admin/personal?buscar=NO-EXISTE').text
    mem.rol='carga'
    assert c.get('/admin/personal').status_code==302
    assert c.post('/admin/personal',data=campos(codigo='NO-CARGAR')).status_code==302
    assert EmpleadoProductivo.query.count()==1


@pytest.mark.parametrize('seccion',['datos','sueldos','horarios','vacaciones','novedades'])
def test_legajo_completo_secciones_centrales(personal,seccion):
    c,*_=personal;e=nuevo(personal)
    r=c.get(f'/admin/personal/{e.id}?seccion={seccion}')
    assert r.status_code==200,r.text
    assert 'Sueldos e historial' in r.text and 'Vacaciones y licencias' in r.text
    assert 'Personal' in r.text


def test_datos_personales_fechas_validacion_y_concurrencia(personal):
    from models.personal_administrativo import PersonalDetalle
    c,*_=personal;e=nuevo(personal)
    f=editar(e,datos_ampliados_presentados='1',dni='30.000.001',cuil='20-30000001-0',fecha_nacimiento='1990-01-01',fecha_ingreso='2024-01-01',email='prueba@example.test',telefono='000123',categoria='Oficial',modalidad='Jornada completa')
    assert c.post('/admin/personal',data=f).status_code==302
    d=db.session.get(PersonalDetalle,e.id);assert d.dni=='30000001' and d.organizacion_id==e.organizacion_id
    assert d.fecha_ingreso.isoformat()=='2024-01-01' and d.telefono=='000123'
    assert c.post('/admin/personal',data=f|{'nombre':'Obsoleto'}).status_code==400
    assert c.post('/admin/personal',data=editar(e,datos_ampliados_presentados='1',fecha_ingreso='2026-01-01',fecha_egreso='2025-01-01',nombre='No guardar')).status_code==400
    db.session.expire_all();assert e.nombre!='No guardar' and d.dni=='30000001'


def test_sueldo_central_actualiza_recurso_y_conserva_historia(personal):
    from services.recursos_productivos import recalcular_tarifa_recurso
    c,org,_,u,*_=personal;e=nuevo(personal)
    post=dict(_csrf_token='csrf-personal',seccion='sueldos',accion='guardar_sueldo',version_actual='',sueldo_base='1000',adicionales='100',otros_costos='0',porcentaje_cargas='10',horas_mensuales='100',horas_productivas='80',porcentaje_productivo='100',ubicacion_trabajo='Taller',tipo_funcion='directa')
    assert c.post(f'/admin/personal/{e.id}',data=post).status_code==302
    db.session.expire_all();v=EmpleadoCostoVersion.query.filter_by(empleado_id=e.id,vigente=True).one();assert v.costo_mensual_total_centavos==120000
    recurso=crear_empleado(organizacion_id=org.id,unidad_negocio_id=u.id,codigo='equipo-sueldo',nombre='Equipo',sector='Taller',Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,EmpleadoProductivo=EmpleadoProductivo,db_session=db.session)
    recurso.tipo_registro='recurso';db.session.commit();vincular_empleado(recurso,e,porcentaje_dedicacion=100,RecursoEmpleadoProductivo=RecursoEmpleadoProductivo,db_session=db.session)
    recalcular_tarifa_recurso(recurso,EmpleadoCostoVersion=EmpleadoCostoVersion,db_session=db.session)
    post.update(version_actual=str(v.id),sueldo_base='2000')
    assert c.post(f'/admin/personal/{e.id}',data=post).status_code==302
    db.session.expire_all();vigentes=EmpleadoCostoVersion.query.filter_by(vigente=True).all()
    assert {x.costo_mensual_total_centavos for x in vigentes}=={230000}
    assert EmpleadoCostoVersion.query.filter_by(empleado_id=e.id).count()==2
    assert c.post(f'/admin/personal/{e.id}',data=post).status_code==400
    assert c.get(f'/admin/personal/{e.id}?seccion=sueldos').status_code==200


def test_horarios_nocturnos_conflictos_y_cancelacion(personal):
    from models.personal_administrativo import HorarioPersonal
    c,*_=personal;e=nuevo(personal);url=f'/admin/personal/{e.id}'
    f=dict(_csrf_token='csrf-personal',seccion='horarios',accion='crear_horario',dia_semana='6',entrada='22:00',salida='06:00',nocturno='1',pausa_minutos='30',desde='2026-10-01')
    assert c.post(url,data=f).status_code==302
    assert c.post(url,data=f|dict(dia_semana='0',entrada='05:00',salida='10:00',nocturno='0')).status_code==400
    h=HorarioPersonal.query.one();assert h.nocturno
    assert c.post(url,data=dict(_csrf_token='csrf-personal',seccion='horarios',accion='cancelar_horario',registro_id=h.id)).status_code==302
    assert HorarioPersonal.query.one().estado=='cancelado'
    assert c.post(url,data=f).status_code==302
    assert EmpleadoCostoVersion.query.count()==0


def test_vacaciones_licencias_sin_solapamiento_ni_impacto_salarial(personal):
    from models.personal_administrativo import AusenciaPersonal
    c,*_=personal;e=nuevo(personal);url=f'/admin/personal/{e.id}'
    f=dict(_csrf_token='csrf-personal',seccion='vacaciones',accion='crear_ausencia',tipo='vacaciones',desde='2026-11-01',hasta='2026-11-14',dias_computados='14',periodo='2026',detalle='Vacaciones de prueba')
    assert c.post(url,data=f).status_code==302
    assert c.post(url,data=f|{'tipo':'licencia'}).status_code==400
    a=AusenciaPersonal.query.one();assert a.estado=='planificada' and a.dias_computados==14
    assert c.post(url,data=dict(_csrf_token='csrf-personal',seccion='vacaciones',accion='cancelar_ausencia',registro_id=a.id)).status_code==302
    assert AusenciaPersonal.query.one().estado=='cancelada'
    assert EmpleadoCostoVersion.query.count()==0


def test_preparacion_aditiva_idempotente_y_guardia(personal,monkeypatch):
    from scripts.preparar_personal import preparar
    c,*_=personal;e=nuevo(personal)
    assert c.post('/admin/personal/preparar',data={'_csrf_token':'csrf-personal'}).status_code==400
    monkeypatch.setenv('SISTEMA_FIERRO_ENTORNO','staging');monkeypatch.setenv('MODO_LABORATORIO_DESCONECTADO','true')
    assert c.post('/admin/personal/preparar',data={'_csrf_token':'csrf-personal'}).status_code==302
    preparar(db.engine);assert EmpleadoProductivo.query.count()==1 and e.nombre=='Persona ficticia'


def test_sueldo_rollback_si_no_puede_recalcular_un_equipo(personal,monkeypatch):
    import services.personal_legajo as servicio
    c,*_=personal;e=nuevo(personal)
    f=dict(_csrf_token='csrf-personal',seccion='sueldos',accion='guardar_sueldo',version_actual='',sueldo_base='1000',horas_mensuales='100',horas_productivas='80',porcentaje_productivo='100',ubicacion_trabajo='Taller',tipo_funcion='directa')
    def falla(*a,**k):raise ValueError('Tarifa dependiente no disponible')
    monkeypatch.setattr(servicio,'recalcular_recursos_del_empleado',falla)
    r=c.post(f'/admin/personal/{e.id}',data=f)
    assert r.status_code==400 and 'Tarifa dependiente no disponible' in r.text
    assert EmpleadoCostoVersion.query.count()==0 and EmpleadoProductivo.query.count()==1
    assert 'personal-accion-error' in r.text


def test_configuracion_general_y_distribucion_en_personal(personal):
    from werkzeug.datastructures import MultiDict
    c,*_=personal;e=nuevo(personal);url=f'/admin/personal/{e.id}'
    f=dict(_csrf_token='csrf-personal',seccion='sueldos',accion='guardar_sueldo',version_actual='',sueldo_base='1000',horas_mensuales='100',horas_productivas='80',porcentaje_productivo='100',ubicacion_trabajo='Taller',tipo_funcion='directa')
    assert c.post(url,data=f).status_code==302
    assert c.post(url,data=dict(_csrf_token='csrf-personal',seccion='sueldos',accion='configurar_porcentaje_costo_laboral',porcentaje_cargas_general='25')).status_code==302
    db.session.expire_all();v=EmpleadoCostoVersion.query.filter_by(empleado_id=e.id,vigente=True).one()
    assert v.cargas_sociales_centavos==25000 and v.numero_version==2
    distrib=MultiDict([('_csrf_token','csrf-personal'),('seccion','sueldos'),('accion','configurar_distribucion_laboral'),('distribucion_unidad_id',str(e.unidad_negocio_id)),('distribucion_porcentaje','100'),('distribucion_ubicacion','Taller'),('distribucion_funcion','directa')])
    assert c.post(url,data=distrib).status_code==302
    assert EmpleadoDistribucionVersion.query.one().empleado_id==e.id
    assert c.get(url+'?seccion=sueldos').status_code==200


def test_sin_esquema_no_hay_guardado_parcial_y_preparacion_sin_copias(personal,monkeypatch):
    from models.personal_administrativo import TABLAS_PERSONAL
    c,*_=personal;e=nuevo(personal)
    db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS_PERSONAL)))
    r=c.get('/admin/personal');assert r.status_code==200 and 'Preparar los datos ampliados' in r.text
    r=c.post('/admin/personal',data=campos(codigo='NO-PARCIAL',datos_ampliados_presentados='1'))
    assert r.status_code==400 and EmpleadoProductivo.query.count()==1
    monkeypatch.setenv('SISTEMA_FIERRO_ENTORNO','staging');monkeypatch.setenv('MODO_LABORATORIO_DESCONECTADO','true')
    assert c.post('/admin/personal/preparar',data={'_csrf_token':'csrf-personal'}).status_code==302
    assert EmpleadoProductivo.query.count()==1


def test_perfil_no_revela_otro_tenant_y_dni_no_se_duplica(personal):
    c,org,otra,u,*_=personal;e=nuevo(personal)
    assert c.post('/admin/personal',data=editar(e,datos_ampliados_presentados='1',dni='30000001',fecha_ingreso='2020-01-01')).status_code==302
    r=c.post('/admin/personal',data=campos(codigo='SEGUNDO',datos_ampliados_presentados='1',dni='30000001'))
    assert r.status_code==400 and EmpleadoProductivo.query.count()==1
    ajeno=crear_empleado(organizacion_id=otra.id,unidad_negocio_id=None,codigo='otro',nombre='Privado',sector='Otro',Organizacion=Organizacion,UnidadNegocio=UnidadNegocio,EmpleadoProductivo=EmpleadoProductivo,db_session=db.session)
    assert c.get(f'/admin/personal/{ajeno.id}').status_code==404
    assert c.post(f'/admin/personal/{ajeno.id}',data={'_csrf_token':'csrf-personal','accion':'guardar_sueldo'}).status_code==404


def test_ausencia_reutiliza_novedad_y_ve_licencias_anteriores(personal):
    from models.personas import NovedadLaboralPreparatoria
    from models.personal_administrativo import AusenciaPersonal
    from services.personas_preparatorias import crear_novedad
    c,*_=personal;e=nuevo(personal)
    crear_novedad({'tipo':'licencia','fecha_desde':'2026-12-01','fecha_hasta':'2026-12-05','detalle':'Licencia anterior'},empleado=e,organizacion_id=e.organizacion_id,unidad_negocio_id=e.unidad_negocio_id,Novedad=NovedadLaboralPreparatoria,db_session=db.session)
    url=f'/admin/personal/{e.id}';f=dict(_csrf_token='csrf-personal',seccion='vacaciones',accion='crear_ausencia',tipo='vacaciones',desde='2026-12-03',hasta='2026-12-04',detalle='Superpuesta')
    assert c.post(url,data=f).status_code==400
    assert c.post(url,data=f|dict(desde='2026-12-10',hasta='2026-12-12')).status_code==302
    a=AusenciaPersonal.query.one();assert a.novedad.empleado_id==e.id and NovedadLaboralPreparatoria.query.count()==2
    r=c.get(url+'?seccion=vacaciones');assert 'Licencia anterior' in r.text
    assert c.post(url,data=dict(_csrf_token='csrf-personal',seccion='vacaciones',accion='cancelar_ausencia',registro_id=a.id)).status_code==302
    assert a.novedad.estado=='cancelada' and not a.novedad.aprobada and not a.novedad.afecta_nomina


def test_empleado_compartido_tiene_vacaciones_sin_duplicar_identidad(personal):
    from models.personal_administrativo import AusenciaPersonal
    c,*_=personal
    assert c.post('/admin/personal',data=campos(codigo='COMPARTIDO')).status_code==302
    e=EmpleadoProductivo.query.filter_by(codigo='compartido').one()
    f=dict(_csrf_token='csrf-personal',seccion='vacaciones',accion='crear_ausencia',tipo='vacaciones',desde='2026-12-01',hasta='2026-12-03',detalle='Prueba compartida')
    assert c.post(f'/admin/personal/{e.id}',data=f).status_code==302
    assert AusenciaPersonal.query.one().empleado_id==e.id and EmpleadoProductivo.query.count()==1
