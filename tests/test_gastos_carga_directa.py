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
