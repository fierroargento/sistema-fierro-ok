"""Separación entre unidades, proveedor compartido y formularios/importaciones ajenos."""
from types import SimpleNamespace
import pytest
from extensions import db
from test_producto_ficha_maestra import entorno
from models.unidad_negocio import UnidadNegocio
from models.compras import ProveedorCompra, OrdenCompra
from models.usuario_sistema import UsuarioSistema
from models.existencia_sucursal import ExistenciaSucursal
from models.inventario_saas import ItemInventario
from models.sucursal_operativa import SucursalOperativa
from models.importacion_masiva_costo import ImportacionMasivaCosto
from models.proveedor_unidad import ProveedorUnidad
from scripts.preparar_proveedores_unidad import preparar
from services.proveedores_unidad import consulta,exigir,vincular,vincular_por_identidad,previsualizar
from services.importacion_proveedores_compra import aplicar_proveedores


@pytest.fixture()
def datos(entorno):
    app,org,otra,a=entorno
    tablas=[ProveedorCompra.__table__,OrdenCompra.__table__,ImportacionMasivaCosto.__table__]
    db.metadata.create_all(db.engine,tables=tablas)
    b=UnidadNegocio(organizacion_id=org.id,codigo='nautica',nombre='Náutica',activa=True)
    c=UnidadNegocio(organizacion_id=otra.id,codigo='otra',nombre='Ajena',activa=True)
    a.activa=True
    ps=[ProveedorCompra(organizacion_id=o.id,codigo=cod,razon_social=nom,cuit=cuit) for o,cod,nom,cuit in [(org,'A','Privado A','30711111111'),(org,'B','Privado B','30722222222'),(org,'S','Compartido','30733333333'),(otra,'X','Otra empresa','30744444444')]]
    db.session.add_all([b,c]+ps);db.session.flush()
    ordenes=[OrdenCompra(organizacion_id=org.id,unidad_negocio_id=a.id,proveedor_id=ps[0].id,numero='OC-A'),OrdenCompra(organizacion_id=org.id,unidad_negocio_id=b.id,proveedor_id=ps[1].id,numero='OC-B')]
    db.session.add_all(ordenes);db.session.commit()
    preparar(db.engine);preparar(db.engine)
    yield app,org,otra,a,b,c,ps
    db.session.rollback()
    db.metadata.drop_all(db.engine,tables=[ProveedorUnidad.__table__]+list(reversed(tablas)))


def test_migracion_asigna_solo_compras_documentadas(datos):
    _,org,_,a,b,_,ps=datos
    assert [p.id for p in consulta(ProveedorCompra,org.id,a.id,db.session).all()]==[ps[0].id]
    assert [p.id for p in consulta(ProveedorCompra,org.id,b.id,db.session).all()]==[ps[1].id]
    assert ProveedorUnidad.query.count()==2
    assert ProveedorCompra.query.count()==4
    assert OrdenCompra.query.count()==2


def test_compartir_no_duplica_ni_mezcla_ordenes(datos):
    _,org,_,a,b,_,ps=datos
    for u in (a,b):
        vincular_por_identidad('S',ProveedorCompra,org.id,u.id,db.session)
    db.session.commit()
    assert ProveedorCompra.query.count()==4
    assert ProveedorUnidad.query.filter_by(proveedor_id=ps[2].id).count()==2
    assert exigir(ps[2],org.id,a.id,db.session)==ps[2]
    assert exigir(ps[2],org.id,b.id,db.session)==ps[2]
    assert OrdenCompra.query.filter_by(unidad_negocio_id=a.id).count()==1
    assert OrdenCompra.query.filter_by(unidad_negocio_id=b.id).count()==1


def test_rechaza_proveedor_y_unidad_ajenos(datos):
    _,org,_,a,b,c,ps=datos
    with pytest.raises(ValueError,match='unidad activa'):exigir(ps[1],org.id,a.id,db.session)
    with pytest.raises(ValueError):vincular(ps[0],org.id,c.id,db.session)
    with pytest.raises(ValueError):vincular_por_identidad('X',ProveedorCompra,org.id,a.id,db.session)
    assert ProveedorUnidad.query.count()==2


def test_importacion_no_copia_datos_de_proveedor_oculto(datos):
    _,org,_,a,b,_,ps=datos
    vista=previsualizar([{'numero':1,'valores':['B','Nombre aportado']}],{'0':'codigo','1':'razon_social'},Proveedor=ProveedorCompra,organizacion_id=org.id,unidad_id=a.id,session=db.session)
    assert vista[0]['accion']=='rechazado' and vista[0]['proveedor_id'] is None
    assert vista[0]['datos']['cuit'] is None
    assert vista[0]['datos']['razon_social']=='Nombre aportado'
    vista=[dict(numero=1,accion='actualizar',proveedor_id=ps[1].id,datos=dict(razon_social='Manipulado'),errores=[])]
    with pytest.raises(ValueError):aplicar_proveedores(vista,organizacion_id=org.id,ProveedorCompra=ProveedorCompra,db_session=db.session,unidad_negocio_id=a.id)
    assert ps[1].razon_social=='Privado B'


def test_importacion_nueva_vincula_unidad_y_rollback(datos):
    _,org,_,a,b,_,_=datos
    vista=[dict(numero=1,accion='crear',proveedor_id=None,datos=dict(codigo='N',razon_social='Nuevo',estado='activo'),errores=[])]
    aplicar_proveedores(vista,organizacion_id=org.id,ProveedorCompra=ProveedorCompra,db_session=db.session,unidad_negocio_id=a.id,commit=False)
    assert consulta(ProveedorCompra,org.id,a.id,db.session).filter_by(codigo='N').count()==1
    assert consulta(ProveedorCompra,org.id,b.id,db.session).filter_by(codigo='N').count()==0
    db.session.rollback()
    assert ProveedorCompra.query.filter_by(codigo='N').count()==0


def test_sin_esquema_no_lista_general(datos):
    _,org,_,a,*_=datos
    ProveedorUnidad.__table__.drop(db.engine)
    assert consulta(ProveedorCompra,org.id,a.id,db.session).count()==0
    ProveedorUnidad.__table__.create(db.engine)


def test_rutas_contexto_y_lotes_por_unidad(datos,monkeypatch):
    import modules.admin.compras.routes as rutas
    app,org,_,a,b,_,ps=datos
    mem=SimpleNamespace(rol='admin',organizacion_id=org.id,organizacion=org)
    monkeypatch.setattr(rutas,'resolver_tenant_usuario',lambda *args,**kw:mem)
    modelos=dict(UnidadNegocio=UnidadNegocio,ProveedorCompra=ProveedorCompra,ImportacionMasivaCosto=ImportacionMasivaCosto)
    app.register_blueprint(rutas.crear_blueprint_compras(dependencias=dict(db=db,modelos=modelos,usuario_actual=lambda:SimpleNamespace(id=1),UsuarioOrganizacion=object,login_required=lambda f:f,registrar_auditoria=lambda *a,**k:None)))
    app.add_url_rule('/',endpoint='inicio',view_func=lambda:'Inicio')
    app.url_build_error_handlers.append(lambda e,endpoint,values:'/sin-uso/'+endpoint)
    app.context_processor(lambda:dict(rol_actual='admin',csrf_token_value='prueba',csp_nonce='prueba'))
    app.jinja_env.globals.update(puede_crear_pedido=lambda:False,puede_ver_historico=lambda:False,alertas_operativas=lambda:[],fecha_argentina=lambda v:v)
    c=app.test_client()
    with c.session_transaction() as s:s['unidad_negocio_id']=a.id
    r=c.post('/admin/compras/guardar',data=dict(accion='editar_proveedor',proveedor_id=ps[1].id,unidad_contexto_id=a.id))
    assert r.status_code==302 and 'error=' in r.location and ps[1].razon_social=='Privado B'
    r=c.post('/admin/compras/guardar',data=dict(accion='vincular_proveedor',identidad_proveedor='B',unidad_contexto_id=b.id))
    assert 'error=' in r.location and ProveedorUnidad.query.filter_by(proveedor_id=ps[1].id,unidad_negocio_id=a.id).count()==0
    r=c.post('/admin/compras/guardar',data=dict(accion='vincular_proveedor',identidad_proveedor='B',unidad_contexto_id=a.id))
    assert 'ok=' in r.location and ProveedorUnidad.query.filter_by(proveedor_id=ps[1].id,unidad_negocio_id=a.id).count()==1
    lotes=[ImportacionMasivaCosto(organizacion_id=org.id,unidad_negocio_id=u,tipo_datos='proveedores_compra',nombre_archivo=n,estado='cargado',modo='crear_actualizar',encabezados_json='[]',filas_json='[]',mapeo_json='{}') for u,n in [(a.id,'Archivo A'),(b.id,'Archivo B'),(None,'General anterior')]]
    db.session.add_all(lotes);db.session.commit()
    r=c.get('/admin/compras/importar-proveedores?lote='+str(lotes[1].id))
    assert r.status_code==200,r.text
    assert 'Archivo A' in r.text and 'Archivo B' not in r.text and 'General anterior' not in r.text


def test_estado_del_compartido_es_independiente(datos):
    from services.proveedores_unidad import estados,operativo
    _,org,_,a,b,_,ps=datos
    for u in (a,b):vincular(ps[2],org.id,u.id,db.session)
    vista=[dict(numero=1,accion='actualizar',proveedor_id=ps[2].id,datos=dict(codigo='S',razon_social='Compartido',estado='inactivo'),errores=[])]
    aplicar_proveedores(vista,organizacion_id=org.id,ProveedorCompra=ProveedorCompra,db_session=db.session,unidad_negocio_id=a.id)
    assert estados(org.id,a.id,db.session)[ps[2].id]=='inactivo'
    assert estados(org.id,b.id,db.session)[ps[2].id]=='activo'
    assert operativo(ps[2],org.id,b.id,db.session).estado=='activo'
    assert ps[2].estado=='activo'
