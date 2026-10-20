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
from models.costo_producto_version import CostoProductoVersion
from models.costo_producto_detalle import CostoProductoDetalle
from models.usuario_sistema import UsuarioSistema
from scripts.preparar_datos_productos import preparar
from services.productos_datos_generales import leer_formulario_completo, guardar_datos_generales, exigir_ubicacion_producto
from services.productos_ficha_maestra import construir_filas
from test_producto_ficha_maestra import entorno, crear, cambiar, configurar_rutas, form_datos, preview, aplicar


@pytest.fixture()
def completo(entorno):
    app,org,otra,unidad=entorno
    db.metadata.create_all(db.engine,tables=[ProveedorCompra.__table__,SucursalOperativa.__table__,UsuarioSistema.__table__,CostoProductoVersion.__table__,CostoProductoDetalle.__table__])
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
    db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS_DATOS_PRODUCTO))+[ProveedorCompra.__table__,SucursalOperativa.__table__,CostoProductoDetalle.__table__,CostoProductoVersion.__table__,UsuarioSistema.__table__])


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
    db.metadata.create_all(engine,tables=[Organizacion.__table__,Producto.__table__,InsumoProductivo.__table__,ProveedorCompra.__table__,SucursalOperativa.__table__,UsuarioSistema.__table__,CostoProductoVersion.__table__,CostoProductoDetalle.__table__])
    codigo="from sqlalchemy import create_engine; from scripts.preparar_datos_productos import preparar; import sys; print(preparar(create_engine(sys.argv[1]))); assert 'app' not in sys.modules"
    r=subprocess.run([sys.executable,'-c',codigo,str(engine.url)],capture_output=True,text=True,env=os.environ)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'Ficha completa preparada' in r.stdout


def costo_form(**cambios):
    return formulario(costo_maestro_presentado='1',precio_costo='1000,25',iva_pct='21',moneda_costo='ARS',**cambios)


def test_costo_reutiliza_historial_y_conserva_vigencia(completo):
    from services.productos_datos_generales import cargar_datos_productos
    _,org,*_=completo
    p=crear(org)
    guardar(p,costo_form())
    g=ProductoDatosGenerales.query.one(); version=db.session.get(CostoProductoVersion,g.costo_carga_id)
    assert version.costo_total_centavos==100025 and version.moneda=='ARS'
    assert version.tipo=='manual' and version.estado=='preparatorio' and not version.vigente
    assert len(version.detalles)==1 and version.detalles[0].cantidad==1
    assert version.detalles[0].costo_unitario_centavos==100025
    assert g.iva_pct==Decimal('21')
    dto=cargar_datos_productos([p],db.session,org.id)[p.id]
    assert dto['precio_costo']=='1000.25' and dto['moneda_costo']=='ARS'
    # Volver a guardar, o editar desde un cliente previo, no duplica ni borra costos.
    guardar(p,costo_form());guardar(p,formulario(marca='Otra'))
    assert CostoProductoVersion.query.count()==1
    assert g.costo_carga_id==version.id and g.iva_pct==21
    version.estado='vigente';version.vigente=True;db.session.commit()
    f=costo_form();f['precio_costo']='12,34';f['moneda_costo']='USD';f['iva_pct']='10,5'
    guardar(p,f)
    nueva=db.session.get(CostoProductoVersion,g.costo_carga_id)
    assert nueva.id!=version.id and nueva.moneda=='USD' and nueva.costo_total_centavos==1234
    assert version.vigente and version.estado=='vigente' and version.costo_total_centavos==100025
    assert not nueva.vigente and nueva.estado=='preparatorio'
    # IVA no se suma a la base ni se interpreta USD como ARS.
    assert g.iva_pct==Decimal('10.5') and CostoProductoVersion.query.count()==2


@pytest.mark.parametrize('campo,valor',[
    ('precio_costo','-1'),('precio_costo','NaN'),('precio_costo','Infinity'),('precio_costo','1e3'),
    ('precio_costo','1000.001'),('precio_costo','1.234,56'),('precio_costo','1000000000000'),
    ('iva_pct','-0.1'),('iva_pct','100.1'),('iva_pct','NaN'),('iva_pct','1.0000001'),('moneda_costo','EUR')])
def test_costo_iva_moneda_invalidos_rechazados(completo,campo,valor):
    f=costo_form();f[campo]=valor
    with pytest.raises(ValueError): leer_formulario_completo(f,[])
    assert CostoProductoVersion.query.count()==0


def test_costo_vacio_cero_y_quitar_no_borra_historial(completo):
    _,org,*_=completo;p=crear(org)
    f=costo_form();f['precio_costo']='';f['iva_pct']=''
    guardar(p,f);g=ProductoDatosGenerales.query.one()
    assert g.costo_carga_id is None and g.iva_pct is None
    f['precio_costo']='0';f['iva_pct']='0';guardar(p,f)
    v=db.session.get(CostoProductoVersion,g.costo_carga_id)
    assert v.costo_total_centavos==0 and g.iva_pct==0
    f['precio_costo']='';guardar(p,f)
    assert g.costo_carga_id is None and CostoProductoVersion.query.count()==1


def test_costo_rollback_integral_y_huella_concurrente(completo):
    _,org,*_=completo;p=crear(org)
    guardar(p,costo_form());_,filas=construir_filas([p],db.session,org.id);anterior=filas[0]
    f=costo_form();f['precio_costo']='999,99';guardar(p,f)
    with pytest.raises(ValueError,match='cambi'):
        from services.productos_ficha_maestra import guardar_ficha
        guardar_ficha(anterior['datos'],Producto=Producto,db_session=db.session,organizacion_id=org.id,
            producto_id=p.id,huella_esperada=anterior['huella'])
    db.session.rollback()
    # La ruta rechaza íntegramente un costo mal formado: no crea el SKU.
    app=completo[0];configurar_rutas(app,org)
    datos=form_datos(sku='COSTO-RECHAZADO')|costo_form().to_dict();datos['precio_costo']='-1'
    respuesta=app.test_client().post('/admin/productos',data=datos)
    assert respuesta.status_code==200 and b'Precio de costo' in respuesta.data
    assert Producto.query.filter_by(sku='COSTO-RECHAZADO').count()==0
    assert CostoProductoVersion.query.count()==2


def test_costo_no_lee_otra_organizacion_y_rechaza_vinculo_ajeno(completo):
    from services.productos_datos_generales import cargar_datos_productos
    _,org,otra,*_=completo;p=crear(org,sku='PROPIO');q=crear(otra,sku='AJENO-COSTO')
    guardar(q,costo_form());g_ajeno=ProductoDatosGenerales.query.filter_by(producto_id=q.id).one()
    guardar(p,formulario());g=ProductoDatosGenerales.query.filter_by(producto_id=p.id).one()
    g.costo_carga_id=g_ajeno.costo_carga_id;db.session.commit()
    assert cargar_datos_productos([p],db.session,org.id)[p.id]['precio_costo']==''
    with pytest.raises(ValueError,match='no corresponde'):
        guardar(p,costo_form())
    db.session.rollback()


def test_migra_datos_anteriores_sin_perder_campos(tmp_path):
    from sqlalchemy import create_engine,text
    from models.organizacion import Organizacion
    from models.fuentes_costo_productivo import InsumoProductivo
    engine=create_engine('sqlite:///'+str(tmp_path/'anterior.sqlite'))
    db.metadata.create_all(engine,tables=[Organizacion.__table__,Producto.__table__,InsumoProductivo.__table__,
        ProveedorCompra.__table__,SucursalOperativa.__table__,UsuarioSistema.__table__,CostoProductoVersion.__table__,CostoProductoDetalle.__table__])
    with engine.begin() as c:
        c.execute(text("CREATE TABLE producto_datos_generales (producto_id INTEGER PRIMARY KEY, organizacion_id INTEGER NOT NULL, rubro VARCHAR(120) NOT NULL, subrubro VARCHAR(120) NOT NULL, marca VARCHAR(120) NOT NULL, utilidad_pct NUMERIC(12,6), utilidad_base VARCHAR(20) NOT NULL, sucursales_definidas BOOLEAN NOT NULL, depositos_definidos BOOLEAN NOT NULL, revision INTEGER NOT NULL)"))
        c.execute(text("INSERT INTO producto_datos_generales VALUES (1,1,'Ferretería','','Fierro',30,'costo',0,0,7)"))
    preparar(engine);preparar(engine)
    with engine.connect() as c:
        fila=c.execute(text('SELECT * FROM producto_datos_generales')).mappings().one()
        assert fila['rubro']=='Ferretería' and fila['revision']==7 and fila['utilidad_pct']==30
        assert fila['costo_carga_id'] is None and fila['iva_pct'] is None and fila['moneda_costo']=='ARS'


def test_ruta_guarda_costo_y_reabre_con_moneda_iva(completo):
    from models.perfil_costeo_producto import PerfilCosteoProducto
    app,org,*_=completo;configurar_rutas(app,org)
    form=form_datos(sku='COSTO-USD')|costo_form().to_dict()
    form.update(precio_costo='12,34',iva_pct='10,5',moneda_costo='USD')
    cliente=app.test_client();r=cliente.post('/admin/productos',data=form)
    assert r.status_code==302
    p=Producto.query.filter_by(sku='COSTO-USD').one()
    v=CostoProductoVersion.query.filter_by(producto_id=p.id).one()
    assert v.costo_total_centavos==1234 and v.moneda=='USD' and not v.vigente
    assert PerfilCosteoProducto.query.filter_by(producto_id=p.id,unidad_negocio_id=None).one().tipo=='simple'
    r=cliente.get(r.location)
    assert b'"precio_costo": "12.34"' in r.data and b'"moneda_costo": "USD"' in r.data
    assert b'"iva_pct": "10.500000"' in r.data


def test_fallo_despues_de_crear_costo_revierte_toda_la_ficha(completo,monkeypatch):
    import services.costos_productos as costos
    from models.perfil_costeo_producto import PerfilCosteoProducto
    original=costos.crear_version_costo
    def fallar(**datos):
        original(**datos)
        raise ValueError('Prueba de rechazo posterior al costo')
    monkeypatch.setattr(costos,'crear_version_costo',fallar)
    app,org,*_=completo;configurar_rutas(app,org)
    form=form_datos(sku='ROLLBACK-COSTO')|costo_form().to_dict()
    r=app.test_client().post('/admin/productos',data=form)
    assert r.status_code==200 and b'rechazo posterior' in r.data
    assert Producto.query.count()==0 and ProductoDatosGenerales.query.count()==0
    assert CostoProductoVersion.query.count()==0 and CostoProductoDetalle.query.count()==0
    assert PerfilCosteoProducto.query.count()==0
