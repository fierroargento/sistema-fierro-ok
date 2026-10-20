"""Alta manual completa, guardado atómico, identidades y fotos sin red."""
import json
from io import BytesIO
from decimal import Decimal
import pytest
from PIL import Image
from werkzeug.datastructures import MultiDict, FileStorage
from sqlalchemy import inspect
from extensions import db
from models.producto import Producto
from models.existencia_sucursal import ExistenciaSucursal
from models.inventario_saas import ItemInventario
from models.catalogo import Catalogo
from models.catalogo_producto import CatalogoProducto
from models.compras import ProveedorCompra
from models.sucursal_operativa import SucursalOperativa
from models.producto_datos_generales import ProductoDatosGenerales, ProductoProveedor, ProductoUbicacion, ProductoCodigoBarras, ProductoImagenMaestra, TABLAS_DATOS_PRODUCTO
from scripts.preparar_datos_productos import preparar
from services.productos_datos_generales import leer_formulario_completo, guardar_datos_generales, exigir_ubicacion_producto
from services.productos_ficha_maestra import construir_filas
from test_producto_ficha_maestra import entorno, crear, cambiar, configurar_rutas, form_datos, preview, aplicar


@pytest.fixture()
def completo(entorno):
    app,org,otra,unidad=entorno
    db.metadata.create_all(db.engine,tables=[ProveedorCompra.__table__,SucursalOperativa.__table__])
    preparar(db.engine)
    p=ProveedorCompra(organizacion_id=org.id,codigo='PROV-1',razon_social='Proveedor Uno',estado='activo')
    q=ProveedorCompra(organizacion_id=org.id,codigo='PROV-2',razon_social='Proveedor Dos',estado='activo')
    x=ProveedorCompra(organizacion_id=otra.id,codigo='AJENO',razon_social='Ajeno',estado='activo')
    a=SucursalOperativa(organizacion_id=org.id,codigo='DEP-1',nombre='Depósito Uno',activa=True)
    b=SucursalOperativa(organizacion_id=org.id,codigo='DEP-2',nombre='Depósito Dos',activa=True)
    z=SucursalOperativa(organizacion_id=otra.id,codigo='AJENA',nombre='Ajena',activa=True)
    db.session.add_all([p,q,x,a,b,z]);db.session.commit()
    yield app,org,otra,unidad,p,q,x,a,b,z
    db.session.rollback()
    db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS_DATOS_PRODUCTO))+[ProveedorCompra.__table__,SucursalOperativa.__table__])


def formulario(**cambios):
    return MultiDict(dict(datos_generales_presentados='1',rubro='Ferretería',subrubro='Tornillos',marca='Fierro',utilidad_pct='30',utilidad_base='costo',proveedores_json='[]',sucursales_json='[]',depositos_json='[]',codigos_barras_json='[]',imagenes_conservar_json='[]',imagen_principal='')|cambios)


def imagen(color='red',nombre='producto.png'):
    b=BytesIO();Image.new('RGB',(12,10),color).save(b,format='PNG');b.seek(0)
    return FileStorage(b,filename=nombre)


def guardar(p,form=None,archivos=()):
    d=leer_formulario_completo(form or formulario(),archivos)
    guardar_datos_generales(p,d,db.session);db.session.commit()
    return d


def test_preparacion_aditiva_idempotente_y_sin_clasificar_legacy(completo):
    _,org,*_=completo
    p=crear(org)
    assert 'ya estaba preparada' in preparar(db.engine)
    assert ProductoDatosGenerales.query.count()==0
    assert Producto.query.one().sku==p.sku
    assert inspect(db.engine).has_table('producto_proveedor')


def test_proveedor_codigo_repetible_entre_proveedores_no_entre_productos_mismo_proveedor(completo):
    _,org,otra,_,p,q,x,*_=completo
    a=crear(org,sku='A');b=crear(org,sku='B');c=crear(otra,sku='C')
    guardar(a,formulario(proveedores_json=json.dumps([{'proveedor_id':p.id,'codigo':'000AbC'}])))
    guardar(b,formulario(proveedores_json=json.dumps([{'proveedor_id':q.id,'codigo':'000AbC'}])))
    guardar(c,formulario(proveedores_json=json.dumps([{'proveedor_id':x.id,'codigo':'000AbC'}])))
    assert ProductoProveedor.query.count()==3
    assert ProductoProveedor.query.filter_by(producto_id=a.id).one().codigo=='000AbC'
    with pytest.raises(ValueError,match='ya identifica otro producto'):
        guardar(b,formulario(proveedores_json=json.dumps([{'proveedor_id':p.id,'codigo':'000abc'}])))
    db.session.rollback()
    assert ProductoProveedor.query.filter_by(producto_id=b.id).one().proveedor_id==q.id


@pytest.mark.parametrize('campo,valor',[('utilidad_pct','NaN'),('utilidad_pct','-1'),('utilidad_pct','1.0000001'),('utilidad_base','otro'),('subrubro','Sin rubro')])
def test_validacion_de_utilidad_y_subrubro(completo,campo,valor):
    f=formulario(**{campo:valor})
    if campo=='subrubro':f['rubro']=''
    with pytest.raises(ValueError): leer_formulario_completo(f,[])


def test_utilidad_sobre_costo_vs_venta_vacio_y_cero(completo):
    _,org,*_=completo
    p=crear(org)
    guardar(p,formulario(utilidad_pct='150',utilidad_base='costo'))
    assert ProductoDatosGenerales.query.one().utilidad_pct==150
    with pytest.raises(ValueError): leer_formulario_completo(formulario(utilidad_pct='100',utilidad_base='precio_venta'),[])
    guardar(p,formulario(utilidad_pct='30,5',utilidad_base='precio_venta'))
    assert ProductoDatosGenerales.query.one().utilidad_pct==Decimal('30.5')
    guardar(p,formulario(utilidad_pct=''))
    assert ProductoDatosGenerales.query.one().utilidad_pct is None
    guardar(p,formulario(utilidad_pct='0'))
    assert ProductoDatosGenerales.query.one().utilidad_pct==0


def test_codigos_barras_conservan_ceros_y_no_identifican_dos_productos(completo):
    _,org,otra,*_=completo
    a=crear(org,sku='A');b=crear(org,sku='B');c=crear(otra,sku='C')
    guardar(a,formulario(codigos_barras_json='["000012345", "ABC-123"]'))
    guardar(c,formulario(codigos_barras_json='["000012345"]'))
    with pytest.raises(ValueError,match='ya pertenece'):
        guardar(b,formulario(codigos_barras_json='["000012345"]'))
    db.session.rollback()
    assert ProductoCodigoBarras.query.filter_by(producto_id=a.id).first().codigo=='000012345'
    with pytest.raises(ValueError,match='repetidos'):
        leer_formulario_completo(formulario(codigos_barras_json='["1","1"]'),[])


def test_relaciones_tenant_y_ubicaciones_explicitas(completo):
    _,org,_,_,p,q,x,a,b,z=completo
    prod=crear(org)
    with pytest.raises(ValueError,match='organización'):
        guardar(prod,formulario(proveedores_json=json.dumps([{'proveedor_id':x.id,'codigo':'1'}])))
    db.session.rollback()
    with pytest.raises(ValueError,match='organización'):
        guardar(prod,formulario(depositos_definidos='1',depositos_json=json.dumps([z.id])))
    db.session.rollback()
    guardar(prod,formulario(depositos_definidos='1',depositos_json=json.dumps([a.id]),sucursales_definidas='1',sucursales_json=json.dumps([b.id])))
    exigir_ubicacion_producto(prod,a.id,'deposito',db.session)
    exigir_ubicacion_producto(prod,b.id,'sucursal',db.session)
    with pytest.raises(ValueError,match='no está habilitada'):
        exigir_ubicacion_producto(prod,b.id,'deposito',db.session)
    guardar(prod,formulario(depositos_definidos='1'))
    with pytest.raises(ValueError):exigir_ubicacion_producto(prod,a.id,'deposito',db.session)


def test_imagenes_principal_reemplazo_limites_y_contenido(completo):
    _,org,*_=completo
    p=crear(org)
    guardar(p,formulario(imagen_principal='nueva:1'),[imagen('red'),imagen('blue','otra.png')])
    fotos=ProductoImagenMaestra.query.order_by(ProductoImagenMaestra.id).all()
    assert len(fotos)==2 and fotos[1].principal and fotos[0].ancho==12
    assert not fotos[0].principal and fotos[0].contenido.startswith(b'\x89PNG')
    # Reemplazar la primera por el mismo contenido no crea duplicados ni falla por la restricción.
    guardar(p,formulario(imagenes_conservar_json=json.dumps([fotos[1].id]),imagen_principal='nueva:0'),[imagen('red')])
    assert ProductoImagenMaestra.query.count()==2
    assert sum(i.principal for i in ProductoImagenMaestra.query.all())==1
    with pytest.raises(ValueError,match='5 imágenes'):
        leer_formulario_completo(formulario(),[imagen() for _ in range(6)])
    with pytest.raises(ValueError):leer_formulario_completo(formulario(),[FileStorage(BytesIO(b'fake'),filename='falsa.png')])
    with pytest.raises(ValueError,match='no pertenece al producto'):
        guardar(p,formulario(imagenes_conservar_json='[99999]'))
    db.session.rollback()


def test_masivo_anterior_preserva_ampliacion_y_detecta_huella_vieja(completo):
    _,org,*_=completo
    p=crear(org);guardar(p,formulario(codigos_barras_json='["0001"]'))
    vista=preview(org,[{'sku':p.sku,'nombre':'Cambio masivo'}])
    guardar(p,formulario(marca='Otra',codigos_barras_json='["0001"]'))
    with pytest.raises(ValueError):aplicar(org,vista)
    vista=preview(org,[{'sku':p.sku,'nombre':'Cambio masivo'}]);aplicar(org,vista)
    assert ProductoDatosGenerales.query.one().marca=='Otra'
    assert ProductoCodigoBarras.query.one().codigo=='0001'


def test_ruta_real_guardado_completo_imagen_autorizada_y_rollback(completo):
    app,org,otra,_,p,q,x,a,b,z=completo
    configurar_rutas(app,org);cliente=app.test_client()
    campos=form_datos(sku='NUEVO-COMPLETO')|dict(formulario(proveedores_json=json.dumps([{'proveedor_id':p.id,'codigo':'0007'}]),codigos_barras_json='["0000999"]',depositos_definidos='1',depositos_json=json.dumps([a.id])))
    f=imagen();campos['imagenes_producto']=(f.stream,f.filename)
    r=cliente.post('/admin/productos',data=campos,content_type='multipart/form-data',follow_redirects=True)
    assert r.status_code==200 and 'ficha guardada correctamente' in r.text
    assert 'Clasificación' in r.text and 'Proveedores y códigos externos' in r.text
    producto=Producto.query.filter_by(sku='NUEVO-COMPLETO').one()
    foto=ProductoImagenMaestra.query.one()
    r=cliente.get(f'/admin/productos/{producto.id}/imagenes/{foto.id}')
    assert r.status_code==200 and r.mimetype=='image/png' and r.data.startswith(b'\x89PNG')
    assert 'private' in r.headers['Cache-Control']
    assert cliente.get(f'/admin/productos/{producto.id+99}/imagenes/{foto.id}').status_code==404
    # El rechazo del código de proveedor revierte ficha, imagen y alta completa.
    campos=form_datos(sku='RECHAZADO')|dict(formulario(proveedores_json=json.dumps([{'proveedor_id':p.id,'codigo':'0007'}])))
    r=cliente.post('/admin/productos',data=campos,follow_redirects=True)
    assert 'ya identifica otro producto' in r.text
    assert Producto.query.filter_by(sku='RECHAZADO').count()==0
    assert ProductoImagenMaestra.query.count()==1
    # El endpoint no revela fotos de otra organización.
    import modules.admin.productos.routes as rutas
    from types import SimpleNamespace
    rutas.resolver_tenant_usuario=lambda *args,**kwargs:SimpleNamespace(rol='admin',organizacion_id=otra.id,organizacion=otra)
    assert cliente.get(f'/admin/productos/{producto.id}/imagenes/{foto.id}').status_code==404


def test_busqueda_por_codigo_proveedor_barras_y_clasificacion_sin_duplicar_filas(completo):
    from services.productos_consultas import obtener_panel_productos_plataforma
    _,org,otra,_,proveedor,*_=completo
    p=crear(org,sku='BUSQUEDA');crear(otra,sku='OTRO')
    guardar(p,formulario(proveedores_json=json.dumps([{'proveedor_id':proveedor.id,'codigo':'EXTERNO-009'}]),codigos_barras_json='["0000987"]',marca='Marca de prueba'))
    for busqueda in ('EXTERNO-009','0000987','Marca de prueba','Ferretería','Tornillos'):
        r=obtener_panel_productos_plataforma(Producto,organizacion_id=org.id,filtro_sku=busqueda)
        assert [x.id for x in r['productos']]==[p.id]
        r=obtener_panel_productos_plataforma(Producto,organizacion_id=otra.id,filtro_sku=busqueda)
        assert r['productos']==[]


def test_no_quita_deposito_con_saldos_y_bloquea_movimiento_fuera_de_permisos(completo):
    from services.inventario_nucleo import registrar_movimiento
    _,org,_,_,p,q,x,a,b,z=completo
    producto=crear(org)
    guardar(producto,formulario(depositos_definidos='1',depositos_json=json.dumps([a.id])))
    db.metadata.create_all(db.engine,tables=[ItemInventario.__table__,ExistenciaSucursal.__table__])
    e=ExistenciaSucursal(organizacion_id=org.id,producto_id=producto.id,sucursal_operativa_id=a.id,stock_actual=3,stock_reservado=0,stock_bloqueado=0,stock_transito=1,control_activo=False)
    db.session.add(e);db.session.commit()
    with pytest.raises(ValueError,match='saldo o compromisos'):
        guardar(producto,formulario(depositos_definidos='1',depositos_json=json.dumps([b.id])))
    db.session.rollback()
    assert ProductoUbicacion.query.filter_by(tipo='deposito').one().sucursal_operativa_id==a.id
    e.stock_actual=0;e.stock_transito=0;db.session.commit()
    guardar(producto,formulario(depositos_definidos='1',depositos_json=json.dumps([b.id])))
    with pytest.raises(ValueError,match='no está habilitada'):
        registrar_movimiento(e,tipo='ingreso',cantidad=1,motivo='Prueba aislada',MovimientoInventario=None,db_session=db.session)
    assert e.stock_actual==0


def test_imagenes_limite_dos_mb_duplicadas_y_principal_invalida(completo):
    _,org,*_=completo
    p=crear(org)
    with pytest.raises(ValueError,match='repetidas'):
        guardar(p,formulario(),[imagen(),imagen()])
    db.session.rollback()
    with pytest.raises(ValueError,match='principal'):
        guardar(p,formulario(imagen_principal='nueva:9'),[imagen()])
    db.session.rollback()
    contenido=imagen().read()+b'0'*(2*1024*1024)
    with pytest.raises(ValueError,match='2 MB'):
        leer_formulario_completo(formulario(),[FileStorage(BytesIO(contenido),filename='grande.png')])
    assert ProductoImagenMaestra.query.count()==0


def test_preparacion_en_proceso_independiente_sin_importar_app(tmp_path):
    import subprocess,sys,os
    from sqlalchemy import create_engine
    from models.organizacion import Organizacion
    from models.fuentes_costo_productivo import InsumoProductivo
    engine=create_engine('sqlite:///'+str(tmp_path/'prueba.sqlite'))
    db.metadata.create_all(engine,tables=[Organizacion.__table__,Producto.__table__,InsumoProductivo.__table__,ProveedorCompra.__table__,SucursalOperativa.__table__])
    codigo="from sqlalchemy import create_engine; from scripts.preparar_datos_productos import preparar; import sys; print(preparar(create_engine(sys.argv[1]))); assert 'app' not in sys.modules"
    r=subprocess.run([sys.executable,'-c',codigo,str(engine.url)],capture_output=True,text=True,env=os.environ)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'Ficha completa preparada' in r.stdout
