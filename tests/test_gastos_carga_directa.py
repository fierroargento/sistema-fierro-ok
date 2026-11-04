"""Gastos y pagos abren aunque existan recetas caras o inválidas."""
from types import SimpleNamespace
import pytest
from extensions import db
from test_reparto_gasto_sector import reparto
from test_producto_ficha_maestra import entorno
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion
from models.ajuste_ipc_productivo import ReglaAjusteIPCProductivo, PropuestaAjusteIPCProductivo
from models.cuentas_pagar_productivas import ObligacionCostoProductivo, PagoObligacionCostoProductivo, ReglaObligacionCostoProductivo
from models.fuentes_costo_productivo import CostoFijoProductivo
from services.fuentes_costo_admin import obtener_gastos_unidad

@pytest.fixture
def pantalla(reparto,monkeypatch):
    f,n,m=reparto;app,org,otra,u,_,_,_,costo,_=f
    extra=[ReglaAjusteIPCProductivo,PropuestaAjusteIPCProductivo,ObligacionCostoProductivo,PagoObligacionCostoProductivo,ReglaObligacionCostoProductivo]
    db.metadata.create_all(db.engine,tables=[x.__table__ for x in extra])
    m.update({x.__name__:x for x in extra});m['CostoFijoProductivo']=CostoFijoProductivo
    # No hay modelos de productos, recetas, precios, máquinas ni Personal.
    import modules.admin.comercial.routes as rutas
    monkeypatch.setattr(rutas,'resolver_tenant_usuario',lambda *a,**kw:SimpleNamespace(rol='admin',organizacion_id=org.id,organizacion=org))
    monkeypatch.setattr(rutas,'obtener_fuentes_costo',lambda *a,**kw:pytest.fail('No debe diagnosticar productos'))
    vistas=[]
    monkeypatch.setattr(rutas,'render_template',lambda name,**kw:vistas.append((name,kw)) or name)
    app.register_blueprint(rutas.crear_blueprint_comercial(dependencias=dict(db=db,modelos=m,login_required=lambda f:f,usuario_actual=lambda:SimpleNamespace(id=1),UsuarioOrganizacion=object)))
    with app.test_client().session_transaction() as ses:ses['unidad_negocio_id']=u.id
    yield app,org,u,m,vistas
    db.session.rollback();db.metadata.drop_all(db.engine,tables=[x.__table__ for x in reversed(extra)])

@pytest.mark.parametrize('url,template',[('/admin/gastos','admin_gastos.html'),('/admin/comercial/cuentas-pagar','admin_cuentas_pagar.html')])
def test_rutas_sin_cargar_catalogo(pantalla,url,template):
    app,org,u,m,vistas=pantalla
    with app.test_client() as cliente:
        with cliente.session_transaction() as ses:ses['unidad_negocio_id']=u.id
        r=cliente.get(url)
    assert r.status_code==200 and r.text==template
    assert vistas[-1][1]['costos_fijos'][0].unidad_negocio_id==u.id
    assert 'perfiles_costeo' not in vistas[-1][1]

def test_consulta_directa_respeta_unidad(pantalla):
    app,org,u,m,vistas=pantalla
    datos=obtener_gastos_unidad(org.id,99999,modelos=m,db_session=db.session)
    assert datos['costos_fijos']==[] and datos['obligaciones_costos']==[]


def test_render_gastos_con_reparto_guardado(pantalla,reparto):
    from jinja2 import Environment, ChoiceLoader, DictLoader, FileSystemLoader
    from test_reparto_gasto_sector import guardar
    from services.reparto_gasto_sector import contexto
    from services.presentacion_monetaria import formatear_centavos_ars
    app,org,u,m,vistas=pantalla
    guardar(reparto);db.session.commit()
    datos=obtener_gastos_unidad(org.id,u.id,modelos=m,db_session=db.session)
    env=Environment(loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')]),autoescape=True)
    env.globals['url_for']=lambda endpoint,**kw:'/'+endpoint
    html=env.get_template('admin_gastos.html').render(**datos,**contexto(db.session,org.id),organizacion=org,unidad_activa=u,unidades=[u],formatear_centavos_ars=formatear_centavos_ars)
    assert 'Revisión 1' in html
    assert 'data-reparto-abrir=' in html
    assert 'reparto-sector-card-head' in html
    assert 'configurar_distribucion_costo_fijo' not in html
    # El formato anterior sigue disponible para gastos sin reparto sectorial.
    legacy=env.get_template('admin_gastos.html').render(**datos,reparto_sector_preparado=True,repartos_sector={},areas_reparto=[],organizacion=org,unidad_activa=u,unidades=[u],formatear_centavos_ars=formatear_centavos_ars)
    assert 'value="80"' in legacy and 'value="75"' in legacy


def test_guardar_calendario_completa_octubre_sin_duplicar(pantalla):
    from datetime import date
    from services.cuentas_pagar_productivas import configurar_regla_obligacion, generar_obligaciones_recurrentes
    from models.fuentes_costo_productivo import CostoFijoVersion
    app,org,u,m,vistas=pantalla
    costo=CostoFijoProductivo.query.filter_by(unidad_negocio_id=u.id).first()
    regla=configurar_regla_obligacion(costo,organizacion_id=org.id,frecuencia_meses=1,periodo_inicio='2026-11',dia_vencimiento=1,meses_anticipacion=2,activa=True,observacion=None,usuario_id=None,ReglaObligacionCostoProductivo=ReglaObligacionCostoProductivo,db_session=db.session)
    args=dict(ObligacionCostoProductivo=ObligacionCostoProductivo,CostoFijoVersion=CostoFijoVersion,db_session=db.session,hoy=date(2026,11,4))
    assert len(generar_obligaciones_recurrentes(regla,**args))==3
    originales={x.id:x.importe_centavos for x in ObligacionCostoProductivo.query.all()}
    regla.periodo_inicio=date(2026,9,1);db.session.commit()
    assert generar_obligaciones_recurrentes(regla,**args)==[]
    nuevas=generar_obligaciones_recurrentes(regla,completar_desde_inicio=True,**args)
    assert {x.periodo for x in nuevas}=={date(2026,9,1),date(2026,10,1)}
    assert generar_obligaciones_recurrentes(regla,completar_desde_inicio=True,**args)==[]
    assert ObligacionCostoProductivo.query.count()==5
    assert {x.id:x.importe_centavos for x in ObligacionCostoProductivo.query.all() if x.id in originales}==originales
