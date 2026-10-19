"""Pruebas con DB real aislada del maestro, lotes y límites de uso."""
from io import BytesIO
from types import SimpleNamespace
from pathlib import Path
import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

from extensions import db
from models.organizacion import Organizacion
from models.unidad_negocio import UnidadNegocio
from models.producto import Producto
from models.producto_ficha_maestra import ProductoFichaMaestra
from models.fuentes_costo_productivo import InsumoProductivo
from models.perfil_costeo_producto import PerfilCosteoProducto, ComboProductoComponente
from services.productos_ficha_maestra import guardar_ficha, construir_filas, huella, datos_de_formulario
from services.producto_habilitaciones import exigir_uso_producto, exigir_uso_insumo
from services.importacion_maestro_productos import leer_lote, previsualizar_lote, firmar_lote, aplicar_lote, plantilla_csv
from services.perfiles_costeo import crear_o_actualizar_perfil, agregar_componente_combo
from scripts.preparar_ficha_productos import preparar


@pytest.fixture()
def entorno():
    app = Flask(__name__, template_folder=str(Path('templates').resolve()), static_folder=str(Path('static').resolve()))
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SECRET_KEY='solo-test', TESTING=True)
    db.init_app(app)
    with app.app_context():
        tablas = [Organizacion.__table__, UnidadNegocio.__table__, Producto.__table__,
            InsumoProductivo.__table__, PerfilCosteoProducto.__table__, ComboProductoComponente.__table__]
        db.metadata.create_all(db.engine, tables=tablas)
        org = Organizacion(nombre='Pruebas', slug='pruebas')
        otra = Organizacion(nombre='Otra', slug='otra')
        db.session.add_all([org, otra]); db.session.flush()
        unidad = UnidadNegocio(organizacion_id=org.id, codigo='uat', nombre='UAT')
        db.session.add(unidad); db.session.commit()
        import modules.admin.productos.routes as rutas
        resolver_original = rutas.resolver_tenant_usuario
        yield app, org, otra, unidad
        rutas.resolver_tenant_usuario = resolver_original
        db.session.remove()
        db.metadata.drop_all(db.engine, tables=[ProductoFichaMaestra.__table__] + tablas)


def datos(sku='UAT-1', **cambios):
    base = dict(sku=sku, nombre='Artículo', descripcion='Descripción', linea='Laser', tipo='simple',
        unidad_medida='unidad', activo=True, habilita_compra=True, habilita_venta=True,
        habilita_insumo=True, habilita_componente=True, insumo_id=None,
        peso_gr=3200, alto_cm=5, ancho_cm=42, largo_cm=36, permite_correo=True,
        permite_via_cargo=False, requiere_revision_logistica=True, observacion_logistica='Conservar')
    return base | cambios


def crear(org, **cambios):
    return guardar_ficha(datos(**cambios), Producto=Producto, db_session=db.session, organizacion_id=org.id)


def cambiar(producto, **cambios):
    _, filas = construir_filas([producto], db.session, producto.organizacion_id)
    fila = filas[0]
    return guardar_ficha(fila['datos'] | cambios, Producto=Producto, db_session=db.session,
        organizacion_id=producto.organizacion_id, producto_id=producto.id, huella_esperada=fila['huella'])


def test_esquema_ausente_no_rompe_legacy_y_preparacion_idempotente(entorno):
    _, org, _, _ = entorno
    p = Producto(organizacion_id=org.id, sku='ANTERIOR', descripcion='Anterior', peso_gr=123)
    db.session.add(p); db.session.commit()
    preparado, filas = construir_filas([p], db.session, org.id)
    assert not preparado and not filas[0]['configurado']
    exigir_uso_producto(p, 'venta', db.session)
    with pytest.raises(ValueError, match='todavía no está preparada'):
        crear(org)
    assert 'preparada' in preparar(db.engine)
    assert 'ya preparada' in preparar(db.engine)
    assert Producto.query.one().peso_gr == 123
    assert ProductoFichaMaestra.query.count() == 0


def test_cuatro_usos_simultaneos_misma_identidad_y_destildado(entorno):
    _, org, _, _ = entorno
    preparar(db.engine)
    p = crear(org)
    for uso in ('compra', 'venta', 'insumo', 'componente'):
        exigir_uso_producto(p, uso, db.session)
    cambiar(p, habilita_venta=False)
    assert Producto.query.count() == 1
    with pytest.raises(ValueError, match='Disponible para venta'):
        exigir_uso_producto(p, 'venta', db.session)
    exigir_uso_producto(p, 'insumo', db.session)
    cambiar(p, activo=False)
    with pytest.raises(ValueError):
        exigir_uso_producto(p, 'compra', db.session)
    assert p.sku == 'UAT-1' and p.peso_gr == 3200


@pytest.mark.parametrize('campo,valor', [('tipo','otro'),('peso_gr','NaN'),('alto_cm','abc'),('largo_cm',0),('habilita_compra','tal vez'),('nombre','x'*201)])
def test_invalidos_no_crean_producto(entorno, campo, valor):
    _, org, _, _ = entorno
    preparar(db.engine)
    with pytest.raises(ValueError):
        crear(org, **{campo:valor})
    db.session.rollback()
    assert Producto.query.count() == 0


def test_checkbox_ausente_equivale_a_destildado(entorno):
    form = {k:str(v) for k,v in datos().items() if not k.startswith('habilita_')}
    form['activo'] = '1'; form['permite_correo'] = '1'; form['requiere_revision_logistica'] = '1'; form['insumo_id']=''
    d = datos_de_formulario(form)
    assert not any(d['habilita_'+u] for u in ('compra','venta','insumo','componente'))


def test_tenant_sku_inmutable_y_ficha_obsoleta(entorno):
    _, org, otra, _ = entorno
    preparar(db.engine); p=crear(org)
    _, filas=construir_filas([p],db.session,org.id); fila=filas[0]
    with pytest.raises(ValueError,match='organización'):
        guardar_ficha(datos(),Producto=Producto,db_session=db.session,organizacion_id=otra.id,producto_id=p.id,huella_esperada=fila['huella'])
    with pytest.raises(ValueError,match='SKU identifica'):
        cambiar(p,sku='OTRO')
    cambiar(p,nombre='Actualizado')
    with pytest.raises(ValueError,match='cambió'):
        guardar_ficha(fila['datos'],Producto=Producto,db_session=db.session,organizacion_id=org.id,producto_id=p.id,huella_esperada=fila['huella'])
    assert ProductoFichaMaestra.query.one().nombre == 'Actualizado'


def test_tipo_de_costeo_coherente_y_componente_no_habilitado(entorno):
    _, org, _, unidad = entorno
    preparar(db.engine)
    p=crear(org); combo=crear(org,sku='COMBO',tipo='combo')
    def perfil(producto,tipo):
        return crear_o_actualizar_perfil(organizacion_id=org.id,unidad_negocio_id=unidad.id,
            producto_id=producto.id,tipo=tipo,Producto=Producto,UnidadNegocio=UnidadNegocio,
            PerfilCosteoProducto=PerfilCosteoProducto,db_session=db.session)
    simple=perfil(p,'simple'); cp=perfil(combo,'combo')
    with pytest.raises(ValueError,match='tipo de'):
        perfil(p,'produccion')
    with pytest.raises(ValueError,match='perfiles de costeo'):
        cambiar(p,tipo='produccion')
    cambiar(p,habilita_componente=False)
    with pytest.raises(ValueError,match='Componente de combo'):
        agregar_componente_combo(cp,simple,cantidad='1',ComboProductoComponente=ComboProductoComponente,db_session=db.session)
    assert ComboProductoComponente.query.count()==0
    cambiar(p,habilita_componente=True)
    agregar_componente_combo(cp,simple,cantidad='2',ComboProductoComponente=ComboProductoComponente,db_session=db.session)
    cambiar(p,habilita_componente=False)
    assert ComboProductoComponente.query.one().cantidad == 2


def test_insumo_vinculado_no_duplica_y_respeta_compra_consumo(entorno):
    _,org,otra,_=entorno
    preparar(db.engine)
    i=InsumoProductivo(organizacion_id=org.id,codigo='I1',nombre='Fuente',tipo='materia_prima',unidad_medida='unidad',activo=True)
    db.session.add(i);db.session.commit()
    p=crear(org,insumo_id=i.id,habilita_compra=False)
    exigir_uso_insumo(i,'insumo',db.session)
    with pytest.raises(ValueError,match='Disponible para compra'):
        exigir_uso_insumo(i,'compra',db.session)
    with pytest.raises(ValueError,match='otro producto'):
        crear(org,sku='DUPLICADO',insumo_id=i.id)
    with pytest.raises(ValueError,match='unidad'):
        cambiar(p,unidad_medida='kg')
    with pytest.raises(ValueError,match='organización'):
        crear(otra,sku='OTRO',insumo_id=i.id)
    assert Producto.query.count()==1


def preview(org,filas):
    return previsualizar_lote([{'numero':n+2,'datos':d} for n,d in enumerate(filas)],Producto=Producto,db_session=db.session,organizacion_id=org.id)


def aplicar(org,vista,usuario=1,token=None):
    return aplicar_lote(token or firmar_lote(vista,org.id,usuario,'clave'),organizacion_id=org.id,usuario_id=usuario,secret_key='clave',Producto=Producto,db_session=db.session)


def test_lote_parcial_preserva_logistica_usos_y_es_reimportable(entorno):
    _,org,_,_=entorno
    preparar(db.engine);p=crear(org)
    v=preview(org,[{'sku':p.sku,'nombre':'Nuevo nombre'}])
    assert v[0]['accion']=='actualizar'
    assert [c['campo'] for c in v[0]['cambios']]==['nombre']
    aplicar(org,v)
    f=ProductoFichaMaestra.query.one()
    assert p.peso_gr==3200 and p.observacion_logistica=='Conservar' and f.habilita_venta
    v=preview(org,[{'sku':p.sku,'nombre':'Nuevo nombre'}])
    assert v[0]['accion']=='sin_cambios'
    assert aplicar(org,v)['sin_cambios']==1


def test_lote_duplicado_rechaza_ambas_filas_sin_carga_parcial(entorno):
    _,org,_,_=entorno
    preparar(db.engine)
    v=preview(org,[datos('CJ-MDF-000'),datos('CJ-MDF-000',nombre='Distinto'),datos('VALIDO')])
    assert [f['accion'] for f in v]==['rechazado','rechazado','crear']
    with pytest.raises(ValueError,match='filas rechazadas'):
        aplicar(org,v)
    assert Producto.query.count()==0


def test_lote_obsoleto_roll_back_completo_y_firma_tenant(entorno):
    _,org,otra,_=entorno
    preparar(db.engine);p=crear(org)
    v=preview(org,[datos('NUEVO'),{'sku':p.sku,'nombre':'Lote'}])
    t=firmar_lote(v,org.id,1,'clave')
    cambiar(p,nombre='Manual')
    with pytest.raises(ValueError,match='cambió'):
        aplicar(org,v,token=t)
    assert Producto.query.count()==1 and ProductoFichaMaestra.query.one().nombre=='Manual'
    with pytest.raises(ValueError,match='usuario y organización'):
        aplicar(otra,v,token=t)
    with pytest.raises(ValueError,match='venció o cambió'):
        aplicar(org,v,token=t+'x')


def test_lote_creacion_exige_roles_y_formulas_no_son_datos(entorno):
    _,org,_,_=entorno
    preparar(db.engine)
    v=preview(org,[{'sku':'NUEVO','nombre':'Nuevo','tipo':'simple','unidad_medida':'unidad'},datos('FORMULA',nombre='=HYPERLINK("x")')])
    assert all(f['errores'] for f in v)
    assert 'fórmulas' in v[1]['errores'][0]


def test_plantilla_csv_es_contrato_valido_sin_conexiones(entorno):
    _,org,_,_=entorno
    preparar(db.engine)
    archivo=FileStorage(BytesIO(plantilla_csv().encode()),filename='plantilla.csv')
    v=preview(org,[f['datos'] for f in leer_lote(archivo)])
    assert v[0]['accion']=='crear' and not v[0]['datos']['permite_correo']
    aplicar(org,v)
    assert Producto.query.count()==1


def test_xlsm_original_detecta_conflicto_sin_ejecutar_macros(entorno):
    # Caso sintético equivalente al encabezado de la hoja Productos original.
    from openpyxl import Workbook
    _,org,_,_=entorno
    preparar(db.engine)
    libro=Workbook();s=libro.active;s.title='Productos'
    s.append(['ID Producto','Nombre','Línea','Descripción','Activo (Sí/No)'])
    s.append(['CJ-MDF-000','Caja A','Laser','Descripción A','Sí'])
    s.append(['CJ-MDF-000','Caja B','Laser','Descripción B','Sí'])
    b=BytesIO();libro.save(b);b.seek(0)
    lote=leer_lote(FileStorage(b,filename='planilla.xlsm'))
    v=previsualizar_lote(lote,Producto=Producto,db_session=db.session,organizacion_id=org.id)
    assert all('duplicado' in f['errores'][0] for f in v)
    assert Producto.query.count()==0


def configurar_rutas(app, org):
    import modules.admin.productos.routes as rutas
    usuario = SimpleNamespace(id=1, nombre='UAT')
    rutas.resolver_tenant_usuario = lambda *a, **kw: SimpleNamespace(rol='admin', organizacion_id=org.id, organizacion=org)
    app.register_blueprint(rutas.crear_blueprint_productos(dependencias={
        'db':db,'login_required':lambda f:f,'usuario_actual':lambda:usuario,
        'registrar_auditoria':lambda *a,**kw:None,'UsuarioOrganizacion':None,'Producto':Producto}))
    app.add_url_rule('/', endpoint='inicio',view_func=lambda:'Inicio')
    app.url_build_error_handlers.append(lambda e,endpoint,values:'/sin-uso/'+endpoint)
    app.jinja_env.globals.update(puede_crear_pedido=lambda:False,puede_ver_historico=lambda:False,alertas_operativas=lambda:[])
    app.context_processor(lambda:dict(usuario_logueado=usuario,rol_actual='admin',csrf_token_value='csrf-test',csp_nonce='test'))
    @app.before_request
    def csrf_de_prueba():
        from flask import request, abort
        if request.method=='POST' and request.form.get('_csrf_token')!='csrf-test':
            abort(400)


def form_datos(**cambios):
    base = datos(**cambios)
    for c,v in list(base.items()):
        if isinstance(v,bool):
            if v: base[c]='1'
            else: del base[c]
        elif v is None: base[c]=''
    return base | {'accion':'crear_producto','huella':'nuevo','_csrf_token':'csrf-test'}


def test_ruta_real_plantilla_csrf_guardado_error_y_rechazo_tenant(entorno):
    app,org,otra,_=entorno
    configurar_rutas(app,org)
    cliente=app.test_client()
    r=cliente.get('/admin/productos')
    assert r.status_code==200 and 'pendiente de preparación' in r.text
    preparar(db.engine)
    r=cliente.get('/admin/productos')
    assert r.status_code==200 and 'Base de Datos' in r.text and 'Gestionar' not in r.text
    assert cliente.get('/admin/productos/plantilla.csv').status_code==200
    assert cliente.post('/admin/productos',data={'accion':'crear_producto'}).status_code==400
    r=cliente.post('/admin/productos',data=form_datos(),follow_redirects=True)
    assert r.status_code==200 and 'ficha guardada correctamente' in r.text and 'Gestionar' in r.text
    assert Producto.query.count()==1
    r=cliente.post('/admin/productos',data=form_datos(sku='ERR',nombre=''),follow_redirects=True)
    assert 'Completá nombre' in r.text and Producto.query.count()==1
    ajeno=Producto(organizacion_id=otra.id,sku='AJENO',descripcion='Otro tenant');db.session.add(ajeno);db.session.commit()
    r=cliente.post('/admin/productos',data=form_datos() | {'accion':'editar_producto','producto_id':ajeno.id})
    assert 'organización activa' in r.text
    assert cliente.post('/admin/productos',data={'accion':'eliminar_producto','producto_id':1,'_csrf_token':'csrf-test'}).status_code==200
    assert Producto.query.count()==2


def test_rechazo_compra_y_consumo_en_manejadores_reales(entorno):
    from services.compras_nucleo import crear_orden, agregar_item_orden
    from services.composicion_costo_producto import guardar_insumo
    _,org,_,unidad=entorno
    preparar(db.engine)
    i=InsumoProductivo(organizacion_id=org.id,codigo='I-BLOQ',nombre='Fuente',tipo='materia_prima',unidad_medida='unidad',activo=True)
    db.session.add(i);db.session.commit()
    p=crear(org,insumo_id=i.id,habilita_compra=False,habilita_insumo=False)
    proveedor=SimpleNamespace(organizacion_id=org.id,estado='activo')
    with pytest.raises(ValueError,match='Disponible para compra'):
        crear_orden({},organizacion_id=org.id,unidad_negocio_id=unidad.id,proveedor=proveedor,
            insumo=i,OrdenCompra=None,OrdenCompraItem=None,db_session=db.session)
    orden=SimpleNamespace(organizacion_id=org.id,unidad_negocio_id=unidad.id,estado='borrador')
    with pytest.raises(ValueError,match='Disponible para compra'):
        agregar_item_orden(orden,{},organizacion_id=org.id,insumo=i,OrdenCompraItem=None,db_session=db.session)
    perfil=SimpleNamespace(organizacion_id=org.id,unidad_negocio_id=unidad.id,tipo='produccion')
    with pytest.raises(ValueError,match='Insumo de producción'):
        guardar_insumo(perfil,i,cantidad='1',merma='0',observacion='',Modelo=None,db_session=db.session)
    with pytest.raises(ValueError,match='referencia de insumo'):
        cambiar(p,insumo_id=None)


def test_rechazo_venta_en_alta_de_catalogo_y_disponibilidad(entorno):
    from models.catalogo import Catalogo
    from models.catalogo_producto import CatalogoProducto
    from models.inventario_saas import ItemInventario
    from models.existencia_sucursal import ExistenciaSucursal
    from models.sucursal_operativa import SucursalOperativa
    from services.catalogos_admin_comercial import procesar_accion_catalogo_comercial
    from services.inventario_disponibilidad_comercial import calcular_cantidad_publicable
    _,org,_,unidad=entorno
    preparar(db.engine)
    db.metadata.create_all(db.engine,tables=[Catalogo.__table__,CatalogoProducto.__table__,ItemInventario.__table__])
    p=crear(org,habilita_venta=False)
    catalogo=Catalogo(organizacion_id=org.id,unidad_negocio_id=unidad.id,codigo='CAT',nombre='Catálogo',moneda='ARS',estado='desactivado')
    db.session.add(catalogo);db.session.commit()
    with pytest.raises(ValueError,match='Disponible para venta'):
        procesar_accion_catalogo_comercial('agregar_producto_catalogo',{'catalogo_id':str(catalogo.id),'producto_id':str(p.id)},
            organizacion=org,unidad_activa=unidad,db_session=db.session,
            modelos={'Producto':Producto,'Catalogo':Catalogo,'CatalogoProducto':CatalogoProducto,'UnidadNegocio':UnidadNegocio})
    item=ItemInventario(organizacion_id=org.id,producto_id=p.id,sku=p.sku,nombre='Ítem',tipo='producto',activo=True)
    db.session.add(item);db.session.commit()
    resultado=calcular_cantidad_publicable(politica=SimpleNamespace(activa=True,umbral_publicacion=0),
        existencia=SimpleNamespace(stock_actual=10,stock_reservado=0,stock_bloqueado=0,control_activo=True),
        item=item,vinculo=SimpleNamespace(estado='activo'))
    assert resultado['cantidad_propuesta']==0
    assert any('Disponible para venta' in m for m in resultado['motivos'])
    assert CatalogoProducto.query.count()==0
