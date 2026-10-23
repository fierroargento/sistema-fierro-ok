"""Alta laboral integral y accesos: datos ficticios, sin activar cuentas ni alarmas."""
import pytest
from werkzeug.security import check_password_hash,generate_password_hash
from werkzeug.datastructures import MultiDict
from extensions import db
from models.personal_administrativo import PersonalAcceso, HorarioPersonal
from models.usuario_sistema import UsuarioSistema
from models.usuario_organizacion import UsuarioOrganizacion
from models.fuentes_costo_productivo import EmpleadoProductivo, EmpleadoCostoVersion
from services.personal_accesos import leer_codigo_alarma,estado_accesos
from test_personal_admin import personal,entorno,campos,nuevo,editar

CLAVE='EjemploPersonal-2026'
ALARMA='003712'


def acceso_form(e=None,**kw):
    return (editar(e) if e else campos()) | dict(accesos_presentados='1',revision_accesos='0',acceso_accion='crear',username='persona.test',password=CLAVE,password_confirm=CLAVE,codigo_alarma=ALARMA) | kw


def test_alta_con_sueldo_horario_alarma_y_cuenta_preparada(personal):
    c,org,_,u,*_=personal
    f=MultiDict(acceso_form(unidad_negocio_id=str(u.id),cargar_sueldo_inicial='1',
        inicial_sueldo_base='1000',inicial_adicionales='0',inicial_otros_costos='0',inicial_porcentaje_cargas='10',inicial_horas_mensuales='160',inicial_horas_productivas='60',inicial_porcentaje_productivo='100',inicial_ubicacion_trabajo='Taller',inicial_tipo_funcion='directa',
        cargar_horario_inicial='1',inicial_dias=['0','1'],inicial_entrada='08:00',inicial_salida='16:00',inicial_nocturno='0',inicial_pausa_minutos='30',inicial_desde='2026-10-01'))
    r=c.post('/admin/personal',data=f);assert r.status_code==302,r.text
    e=EmpleadoProductivo.query.one();a=PersonalAcceso.query.one();v=EmpleadoCostoVersion.query.one();user=UsuarioSistema.query.one()
    assert a.empleado_id==e.id and v.empleado_id==e.id and HorarioPersonal.query.count()==2
    assert v.sueldo_base_centavos==100000 and v.cargas_sociales_centavos==10000
    assert check_password_hash(user.password_hash,CLAVE) and user.password_hash!=CLAVE
    assert not user.activo and not a.membresia.activa and a.membresia.organizacion_id==org.id
    assert ALARMA.encode() not in a.codigo_alarma_cifrado
    assert leer_codigo_alarma(e,db.session)==ALARMA
    for url in ['/admin/personal',f'/admin/personal/{e.id}']:
        html=c.get(url).text
        assert CLAVE not in html and ALARMA not in html and user.password_hash not in html
        assert 'persona.test' in html and 'Sueldo' in html
    r=c.post(f'/admin/personal/{e.id}/alarma',data={'_csrf_token':'csrf-personal'})
    assert r.status_code==200 and r.json['codigo']==ALARMA and 'no-store' in r.headers['Cache-Control']


def test_datos_invalidos_revierten_toda_el_alta_y_no_devuelven_secretos(personal):
    c,*_=personal
    f=acceso_form(cargar_horario_inicial='1',inicial_dias=['0'],inicial_entrada='08:00',inicial_salida='08:00',inicial_desde='2026-10-01')
    r=c.post('/admin/personal',data=f)
    assert r.status_code==400 and EmpleadoProductivo.query.count()==0 and UsuarioSistema.query.count()==0
    assert CLAVE not in r.text and ALARMA not in r.text
    f=acceso_form(cargar_sueldo_inicial='1',inicial_sueldo_base='1000',inicial_horas_mensuales='160',inicial_horas_productivas='60',inicial_porcentaje_productivo='100',inicial_ubicacion_trabajo='Taller',inicial_tipo_funcion='directa',password_confirm='distinta')
    r=c.post('/admin/personal',data=f)
    assert r.status_code==400 and EmpleadoProductivo.query.count()==0 and EmpleadoCostoVersion.query.count()==0
    assert UsuarioSistema.query.count()==0 and CLAVE not in r.text and ALARMA not in r.text


def test_alarma_y_clave_vacias_conservan_y_reset_cierra_sesiones(personal):
    c,*_=personal
    assert c.post('/admin/personal',data=acceso_form()).status_code==302
    e=EmpleadoProductivo.query.one();a=PersonalAcceso.query.one();user=UsuarioSistema.query.one();hash_antes=user.password_hash
    f=editar(e)|dict(accesos_presentados='1',revision_accesos=str(a.revision),acceso_accion='conservar',password='',codigo_alarma='')
    assert c.post('/admin/personal',data=f).status_code==302
    assert user.password_hash==hash_antes and leer_codigo_alarma(e,db.session)==ALARMA
    clave_nueva='ClaveNuevaEmpleado2026'
    assert c.post('/admin/personal',data=f|dict(password=clave_nueva,password_confirm=clave_nueva)).status_code==302
    assert check_password_hash(user.password_hash,clave_nueva) and user.session_epoch==1
    # El código original queda cifrado y puede quitarse sólo de manera explícita.
    assert c.post('/admin/personal',data=editar(e)|dict(accesos_presentados='1',revision_accesos=str(a.revision),quitar_codigo_alarma='1')).status_code==302
    assert leer_codigo_alarma(e,db.session)==''


def test_vincular_cuenta_existente_de_misma_org_sin_duplicar(personal):
    c,org,_,_,*_=personal;e=nuevo(personal)
    user=UsuarioSistema(username='ya-existe',nombre='Ya existe',password_hash=generate_password_hash(CLAVE),rol='despacho',activo=True)
    db.session.add(user);db.session.flush();mem=UsuarioOrganizacion(usuario_id=user.id,organizacion_id=org.id,rol='despacho',activa=True);db.session.add(mem);db.session.commit()
    f=editar(e)|dict(accesos_presentados='1',revision_accesos='0',acceso_accion='vincular',usuario_organizacion_id=str(mem.id))
    assert c.post('/admin/personal',data=f).status_code==302
    assert UsuarioSistema.query.count()==1 and mem.activa and user.rol=='despacho'
    assert estado_accesos(e,db.session)['usuario_sistema']=='ya-existe'
    otro=nuevo(personal,codigo='otro')
    assert c.post('/admin/personal',data=editar(otro)|dict(accesos_presentados='1',revision_accesos='0',acceso_accion='vincular',usuario_organizacion_id=str(mem.id))).status_code==400
    assert PersonalAcceso.query.count()==1


def test_rechaza_usuario_ajeno_y_reset_multiorganizacion(personal):
    c,org,otra,_,*_=personal;e=nuevo(personal)
    user=UsuarioSistema(username='multi',nombre='Multi',password_hash=generate_password_hash(CLAVE),rol='carga',activo=True)
    db.session.add(user);db.session.flush();mem=UsuarioOrganizacion(usuario_id=user.id,organizacion_id=otra.id,rol='carga',activa=True);db.session.add(mem);db.session.commit()
    f=editar(e)|dict(accesos_presentados='1',revision_accesos='0',acceso_accion='vincular',usuario_organizacion_id=str(mem.id))
    assert c.post('/admin/personal',data=f).status_code==400
    own=UsuarioOrganizacion(usuario_id=user.id,organizacion_id=org.id,rol='carga',activa=True);db.session.add(own);db.session.commit()
    assert c.post('/admin/personal',data=f|dict(usuario_organizacion_id=str(own.id))).status_code==302
    a=PersonalAcceso.query.one();antes=user.password_hash
    f=editar(e)|dict(accesos_presentados='1',revision_accesos=str(a.revision),acceso_accion='conservar',password=CLAVE,password_confirm=CLAVE)
    assert c.post('/admin/personal',data=f).status_code==400
    assert user.password_hash==antes


def test_revelado_alarma_es_post_csrf_admin_y_no_filtra_por_get(personal):
    c,org,otra,u,m,mem=personal
    assert c.post('/admin/personal',data=acceso_form()).status_code==302
    e=EmpleadoProductivo.query.one();url=f'/admin/personal/{e.id}/alarma'
    assert c.get(url).status_code==405 and c.post(url,data={}).status_code==400
    assert c.post('/admin/personal/999/alarma',data={'_csrf_token':'csrf-personal'}).status_code==404
    mem.rol='carga'
    r=c.post(url,data={'_csrf_token':'csrf-personal'});assert r.status_code==403 and ALARMA not in r.text


def test_revision_de_accesos_rechaza_cambios_obsoletos(personal):
    c,*_=personal
    assert c.post('/admin/personal',data=acceso_form()).status_code==302
    e=EmpleadoProductivo.query.one();a=PersonalAcceso.query.one()
    f=editar(e)|dict(accesos_presentados='1',revision_accesos=str(a.revision),codigo_alarma='008899')
    assert c.post('/admin/personal',data=f).status_code==302
    r=c.post('/admin/personal',data=editar(e)|dict(accesos_presentados='1',revision_accesos=f['revision_accesos'],codigo_alarma='001122'))
    assert r.status_code==400 and leer_codigo_alarma(e,db.session)=='008899'
    assert '001122' not in r.text


def test_preparacion_de_version_anterior_agrega_accesos_sin_perder_datos(personal,monkeypatch):
    from scripts.preparar_personal import preparado
    c,*_=personal;e=nuevo(personal)
    db.metadata.drop_all(db.engine,tables=[PersonalAcceso.__table__])
    assert not preparado(db.engine)
    monkeypatch.setenv('SISTEMA_FIERRO_ENTORNO','staging');monkeypatch.setenv('MODO_LABORATORIO_DESCONECTADO','true')
    r=c.get('/admin/personal');assert r.status_code==200 and 'Preparar Personal' in r.text
    assert c.post('/admin/personal/preparar',data={'_csrf_token':'csrf-personal'}).status_code==302
    assert preparado(db.engine) and EmpleadoProductivo.query.count()==1 and EmpleadoProductivo.query.one().id==e.id


def test_codigo_cifrado_rechaza_alteracion_sin_exponer_el_valor(personal):
    c,*_=personal
    assert c.post('/admin/personal',data=acceso_form()).status_code==302
    e=EmpleadoProductivo.query.one();a=PersonalAcceso.query.one();a.codigo_alarma_cifrado=b'cifrado-invalido';db.session.commit()
    r=c.post(f'/admin/personal/{e.id}/alarma',data={'_csrf_token':'csrf-personal'})
    assert r.status_code==400 and 'no-store' in r.headers['Cache-Control']
    assert ALARMA not in r.text and CLAVE not in r.text
