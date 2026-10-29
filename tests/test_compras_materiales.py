"""Materiales de Compras: fuente única, precio histórico y límites de unidad."""
import pytest
from types import SimpleNamespace
from extensions import db
from models.organizacion import Organizacion
from models.fuentes_costo_productivo import InsumoProductivo as I, InsumoPrecioVersion as V
from models.unidad_negocio import UnidadNegocio
from test_personal_admin import personal,entorno

@pytest.fixture()
def materiales(personal,monkeypatch):
    import modules.admin.compras.routes as rutas
    c,org,otra,u,m,mem=personal
    monkeypatch.setattr(rutas,'resolver_tenant_usuario',lambda *args,**kw:mem)
    m.update(Organizacion=Organizacion,InsumoProductivo=I,InsumoPrecioVersion=V)
    db.metadata.create_all(db.engine,tables=[V.__table__])
    c.application.register_blueprint(rutas.crear_blueprint_compras(dependencias=dict(db=db,modelos=m,usuario_actual=lambda:SimpleNamespace(id=1),UsuarioOrganizacion=m['UsuarioOrganizacion'],login_required=lambda f:f,registrar_auditoria=lambda *a,**k:None)))
    b=UnidadNegocio(organizacion_id=org.id,codigo='naut',nombre='Náutica',activa=True);db.session.add(b);db.session.commit()
    rows=[I(organizacion_id=o,unidad_negocio_id=unit,codigo=cod,nombre=nom,tipo='materia_prima',unidad_medida='metro') for o,unit,cod,nom in [(org.id,u.id,'A','Material propio'),(org.id,b.id,'B','Material otra unidad'),(org.id,None,'C','Material sin asignar'),(otra.id,None,'X','Material ajeno')]]
    db.session.add_all(rows);db.session.commit()
    yield c,org,u,b,rows,mem
    db.session.rollback();V.__table__.drop(db.engine)

def form(u,**kw):
    return dict(_csrf_token='csrf-personal',unidad_contexto_id=str(u.id),accion='precio',moneda='ARS',precio_unitario='150,25',version_actual='')|kw

def test_consulta_historial_y_actualizacion_sin_fuga(materiales):
    c,org,u,b,rows,_=materiales
    r=c.get('/admin/compras/materiales');assert r.status_code==200,r.text
    assert rows[0].nombre in r.text and all(i.nombre not in r.text for i in rows[1:])
    assert c.get('/admin/compras/materiales?ver='+str(rows[1].id)).status_code==404
    r=c.post('/admin/compras/materiales',data=form(u,insumo_id=str(rows[0].id),proveedor_referencia='Referencia propia'))
    assert r.status_code==302
    v=V.query.one();assert v.precio_unitario_centavos==15025 and v.vigente
    r=c.get('/admin/compras/materiales?ver='+str(rows[0].id));assert r.status_code==200 and 'Referencia propia' in r.text and 'material-historial' in r.text
    assert c.post('/admin/compras/materiales',data=form(u,insumo_id=str(rows[0].id))).status_code==400
    assert V.query.count()==1
    r=c.post('/admin/compras/materiales',data=form(u,insumo_id=str(rows[0].id),version_actual=str(v.id),precio_unitario='200'))
    assert r.status_code==302 and V.query.count()==2
    db.session.expire_all();assert not v.vigente and V.query.filter_by(vigente=True).one().precio_unitario_centavos==20000

def test_guardado_rechaza_contexto_ids_y_errores_atomicos(materiales):
    c,org,u,b,rows,_=materiales
    assert c.post('/admin/compras/materiales',data=form(u,insumo_id=str(rows[1].id))).status_code==400
    assert c.post('/admin/compras/materiales',data=form(b,insumo_id=str(rows[0].id))).status_code==400
    assert c.post('/admin/compras/materiales',data=form(u,accion='crear',codigo='MAL',nombre='No guardar',tipo='materia_prima',unidad_medida='m',precio_unitario='-1')).status_code==400
    assert not I.query.filter_by(codigo='mal').first() and V.query.count()==0
    r=c.post('/admin/compras/materiales',data=form(u,accion='crear',codigo='NUEVO',nombre='Material nuevo',tipo='consumible',unidad_medida='unidad',precio_unitario=''))
    assert r.status_code==302 and I.query.filter_by(codigo='nuevo').one().unidad_negocio_id==u.id

def test_roles_y_csrf_materiales(materiales):
    c,org,u,b,rows,mem=materiales
    f=form(u,insumo_id=str(rows[0].id));del f['_csrf_token']
    assert c.post('/admin/compras/materiales',data=f).status_code==400
    mem.rol='carga'
    assert c.get('/admin/compras/materiales').status_code==302
    assert c.post('/admin/compras/materiales',data=form(u,insumo_id=str(rows[0].id))).status_code==302
    assert V.query.count()==0


def test_precio_conserva_presentacion_y_version_por_bulto(materiales):
    c,org,u,b,rows,_=materiales
    from models.insumo_presentacion_compra import InsumoPresentacionCompra as P,InsumoPrecioBultoVersion as B
    db.metadata.create_all(db.engine,tables=[P.__table__,B.__table__])
    try:
        db.session.add(P(insumo_id=rows[0].id,organizacion_id=org.id,cantidad_bulto=6,medidas_origen='Barra de 6 m'))
        db.session.commit()
        r=c.post('/admin/compras/materiales',data=form(u,insumo_id=str(rows[0].id),precio_unitario='200'))
        assert r.status_code==302
        v=V.query.one();base=db.session.get(B,v.id)
        assert v.precio_unitario_centavos==20000 and base.precio_bulto_centavos==120000
        assert base.cantidad_bulto==6 and db.session.get(P,rows[0].id).medidas_origen=='Barra de 6 m'
    finally:
        db.session.rollback();db.metadata.drop_all(db.engine,tables=[B.__table__,P.__table__])
