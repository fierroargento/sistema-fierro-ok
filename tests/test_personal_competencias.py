"""La carga única de competencias vive en el legajo, con registros previos intactos."""
import pytest
from extensions import db
from models.personas import CompetenciaEmpleadoPreparatoria as Competencia
from models.fuentes_costo_productivo import EmpleadoCostoVersion
from services.cierre_personas_preparatorio import registrar_competencia,huella_competencia
from test_personal_admin import personal,entorno,nuevo


def formulario(**kw):
    return dict(_csrf_token='csrf-personal',seccion='competencias',accion='registrar_competencia',
        codigo='SOLD',nombre='Soldadura',nivel='3',vence_el='2027-01-15',observacion='Ejemplo ficticio')|kw


def test_previas_se_ven_en_legajo_sin_migrar_y_se_editan_sin_duplicar(personal):
    c,org,_,u,m,*_=personal;e=nuevo(personal)
    anterior=registrar_competencia(formulario(),empleado=e,organizacion_id=org.id,unidad_negocio_id=u.id,Competencia=Competencia,db_session=db.session)
    ident=anterior.id
    html=c.get(f'/admin/personal/{e.id}?seccion=competencias').text
    assert 'Soldadura' in html and 'Nueva competencia' in html and 'personal-competencia-ver-' in html
    f=formulario(accion='editar_competencia',registro_id=str(ident),huella_competencia=huella_competencia(anterior),nombre='Soldadura MIG',nivel='4')
    assert c.post(f'/admin/personal/{e.id}',data=f).status_code==302
    db.session.expire_all();assert Competencia.query.count()==1 and anterior.id==ident and anterior.nombre=='Soldadura MIG'
    assert not anterior.verificada and not anterior.habilita_asignacion
    assert EmpleadoCostoVersion.query.count()==0
    assert c.post(f'/admin/personal/{e.id}',data=f).status_code==400
    assert anterior.nivel==4


def test_alta_desde_legajo_rechaza_duplicados_y_conserva_identidad_y_flags(personal):
    c,*_=personal;e=nuevo(personal)
    assert c.post(f'/admin/personal/{e.id}',data=formulario(verificada='true',habilita_asignacion='true')).status_code==302
    comp=Competencia.query.one();assert comp.empleado_id==e.id and not comp.verificada and not comp.habilita_asignacion
    assert c.post(f'/admin/personal/{e.id}',data=formulario()).status_code==400
    assert Competencia.query.count()==1


@pytest.mark.parametrize('kw',[dict(nivel='6'),dict(vence_el='fecha-mal'),dict(nombre=''),dict(codigo='x'*81),dict(nombre='x'*181),dict(observacion='x'*501)])
def test_validacion_no_guarda_y_reabre_formulario(personal,kw):
    c,*_=personal;e=nuevo(personal)
    r=c.post(f'/admin/personal/{e.id}',data=formulario(**kw));assert r.status_code==400 and 'personal-competencia-nueva' in r.text
    assert Competencia.query.count()==0


def test_compartido_unidad_propia_y_registros_de_otros_legajos_protegidos(personal):
    c,org,otra,u,m,*_=personal;e=nuevo(personal);e.unidad_negocio_id=None;db.session.commit()
    assert c.post(f'/admin/personal/{e.id}',data=formulario(competencia_unidad_id='abc')).status_code==400
    Unidad=m['UnidadNegocio'];ajena=Unidad(organizacion_id=otra.id,codigo='ajena',nombre='Ajena');db.session.add(ajena);db.session.commit()
    assert c.post(f'/admin/personal/{e.id}',data=formulario(competencia_unidad_id=str(ajena.id))).status_code==400
    assert c.post(f'/admin/personal/{e.id}',data=formulario(competencia_unidad_id=str(u.id))).status_code==302
    comp=Competencia.query.one();otro=nuevo(personal,codigo='otro')
    f=formulario(accion='editar_competencia',registro_id=str(comp.id),huella_competencia=huella_competencia(comp),nombre='Ajeno')
    assert c.post(f'/admin/personal/{otro.id}',data=f).status_code==400
    assert comp.nombre=='Soldadura'


def test_admin_y_csrf_obligatorios(personal):
    c,_,_,_,_,mem=personal;e=nuevo(personal)
    f=formulario();del f['_csrf_token']
    assert c.post(f'/admin/personal/{e.id}',data=f).status_code==400
    mem.rol='carga'
    assert c.post(f'/admin/personal/{e.id}',data=formulario()).status_code==302
    assert Competencia.query.count()==0


def test_agenda_sin_carga_duplicada_y_post_viejo_solo_redirige(personal,monkeypatch):
    from modules.admin.personas import routes
    c,org,_,u,m,mem=personal;app=c.application
    monkeypatch.setattr(routes,'resolver_tenant_usuario',lambda *a,**k:mem)
    app.register_blueprint(routes.crear_blueprint_personas(dependencias=dict(db=db,modelos=m,UsuarioOrganizacion=m['UsuarioOrganizacion'],
        login_required=lambda f:f,usuario_actual=lambda:None,registrar_auditoria=lambda *a,**k:None)))
    e=nuevo(personal)
    html=c.get('/admin/personas').text
    assert 'value="registrar_competencia"' not in html and 'Cobertura y vencimientos' in html
    r=c.post('/admin/personas/guardar',data=formulario(empleado_id=str(e.id)))
    assert r.status_code==302 and 'seccion=competencias' in r.location and Competencia.query.count()==0
    assert c.post(f'/admin/personal/{e.id}',data=formulario()).status_code==302
    html=c.get('/admin/personas').text
    assert 'Soldadura' in html and f'/admin/personal/{e.id}?seccion=competencias' in html
