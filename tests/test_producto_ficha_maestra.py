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
    p=crear(org); base=crear(org,sku='BASE')
    combo=crear(org,sku='COMBO',tipo='combo',componentes_combo=[{'sku':base.sku,'cantidad':'1'}],unidad_combo_id=unidad.id)
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
    assert ComboProductoComponente.query.count()==1
    cambiar(p,habilita_componente=True)
    agregar_componente_combo(cp,simple,cantidad='2',ComboProductoComponente=ComboProductoComponente,db_session=db.session)
    cambiar(p,habilita_componente=False)
    assert ComboProductoComponente.query.filter_by(combo_perfil_id=cp.id,componente_perfil_id=simple.id).one().cantidad == 2


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
    assert r.status_code==200 and 'Base de Datos' in r.text and 'data-product-actions="' not in r.text
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


def test_no_stockeable_admite_compra_venta_y_se_reimporta(entorno):
    _,org,_,_=entorno
    preparar(db.engine)
    p=crear(org,no_stockeable=True,permite_correo=False,permite_via_cargo=False)
    f=ProductoFichaMaestra.query.one()
    assert f.no_stockeable and f.tipo=='simple'
    exigir_uso_producto(p,'compra',db.session)
    exigir_uso_producto(p,'venta',db.session)
    _,filas=construir_filas([p],db.session,org.id)
    assert filas[0]['datos']['no_stockeable'] is True
    v=preview(org,[{'sku':p.sku,'nombre':'Servicio'}]);aplicar(org,v)
    assert ProductoFichaMaestra.query.one().no_stockeable
    v=preview(org,[{'sku':p.sku,'no_stockeable':'No'}]);aplicar(org,v)
    assert not ProductoFichaMaestra.query.one().no_stockeable
    assert Producto.query.count()==1


def test_no_stockeable_rechaza_transporte_y_stock_antes_de_mutar(entorno):
    from services.producto_habilitaciones import exigir_producto_stockeable, exigir_recurso_stockeable
    from models.inventario_saas import ItemInventario
    from models.existencia_sucursal import ExistenciaSucursal
    from models.sucursal_operativa import SucursalOperativa
    from services.inventario_nucleo import registrar_movimiento
    _,org,_,_=entorno
    preparar(db.engine)
    with pytest.raises(ValueError,match='envío físico'):
        crear(org,no_stockeable=True)
    p=crear(org,no_stockeable=True,permite_correo=False,permite_via_cargo=False)
    with pytest.raises(ValueError,match='No stockeable'):
        exigir_producto_stockeable(p,db.session)
    # Registro ORM sintético sin guardar para comprobar el punto de entrada
    # del movimiento antes de modificar saldos o crear una reserva.
    e=ExistenciaSucursal(organizacion_id=org.id,producto_id=p.id,stock_actual=0,stock_reservado=0,stock_bloqueado=0)
    with pytest.raises(ValueError,match='No stockeable'):
        registrar_movimiento(e,tipo='ingreso',cantidad=1,motivo='Prueba',MovimientoInventario=None,db_session=db.session)
    assert e.stock_actual==0 and e.stock_reservado==0


def test_no_stockeable_no_se_prepara_como_sku_de_inventario(entorno):
    from models.catalogo import Catalogo
    from models.catalogo_producto import CatalogoProducto
    from models.inventario_saas import ItemInventario
    from services.inventario_saas import preparar_items_catalogo
    _,org,_,unidad=entorno
    preparar(db.engine)
    db.metadata.create_all(db.engine,tables=[Catalogo.__table__,CatalogoProducto.__table__,ItemInventario.__table__])
    p=crear(org,no_stockeable=True,permite_correo=False,permite_via_cargo=False)
    c=Catalogo(organizacion_id=org.id,unidad_negocio_id=unidad.id,codigo='SERV',nombre='Servicios',moneda='ARS',estado='desactivado')
    db.session.add(c);db.session.flush()
    inclusion=CatalogoProducto(catalogo_id=c.id,producto_id=p.id,sku_comercial=p.sku,nombre_comercial='Servicio',precio_centavos=0,activo=False,disponible=False)
    db.session.add(inclusion);db.session.commit()
    assert preparar_items_catalogo(org.id,[inclusion],ItemInventario=ItemInventario,db_session=db.session)==0
    assert ItemInventario.query.count()==0


def test_no_stockeable_no_convierte_producto_con_existencias_aun_en_cero(entorno):
    from models.inventario_saas import ItemInventario
    from models.existencia_sucursal import ExistenciaSucursal
    from models.sucursal_operativa import SucursalOperativa
    _,org,_,_=entorno
    preparar(db.engine)
    db.metadata.create_all(db.engine,tables=[SucursalOperativa.__table__,ItemInventario.__table__,ExistenciaSucursal.__table__])
    p=crear(org)
    s=SucursalOperativa(organizacion_id=org.id,codigo='uat',nombre='UAT',activa=False)
    db.session.add(s);db.session.flush()
    e=ExistenciaSucursal(organizacion_id=org.id,producto_id=p.id,sucursal_operativa_id=s.id,stock_actual=0,stock_reservado=0,stock_bloqueado=0,control_activo=False)
    db.session.add(e);db.session.commit()
    with pytest.raises(ValueError,match='ya tiene existencias'):
        cambiar(p,no_stockeable=True,permite_correo=False,permite_via_cargo=False)
    db.session.rollback()
    assert not ProductoFichaMaestra.query.one().no_stockeable
    assert ExistenciaSucursal.query.one().stock_actual==0


def test_preparacion_actualiza_esquema_anterior_sin_perder_roles(entorno):
    from scripts.preparar_ficha_productos import DDL
    from sqlalchemy import text
    _,org,_,_=entorno
    p=Producto(organizacion_id=org.id,sku='ANTERIOR',descripcion='Anterior')
    db.session.add(p);db.session.commit()
    with db.engine.begin() as c:
        c.execute(text(DDL.replace('no_stockeable BOOLEAN NOT NULL DEFAULT FALSE,','')))
        c.execute(text("INSERT INTO producto_ficha_maestra (producto_id,organizacion_id,nombre,linea,unidad_medida,tipo,activo,habilita_compra,habilita_venta,habilita_insumo,habilita_componente,revision) VALUES (:p,:o,'Anterior','','unidad','simple',1,1,0,1,0,1)"),{'p':p.id,'o':org.id})
    assert 'actualizada con No stockeable' in preparar(db.engine)
    f=ProductoFichaMaestra.query.one()
    assert f.habilita_compra and not f.habilita_venta and f.habilita_insumo and not f.no_stockeable
    assert 'ya preparada' in preparar(db.engine)


@pytest.mark.parametrize('tipo_origen,tipo_destino',[('simple','combo'),('produccion','combo'),('combo','simple'),('combo','produccion')])
def test_combo_exige_otro_sku_en_edicion_e_importacion(entorno,tipo_origen,tipo_destino):
    _,org,_,_=entorno
    preparar(db.engine)
    extra = {}
    if tipo_origen == 'combo':
        crear(org,sku='BASE')
        extra = {'componentes_combo':[{'sku':'BASE','cantidad':'1'}]}
    p=crear(org,tipo=tipo_origen,**extra)
    with pytest.raises(ValueError,match='SKU propios'):
        cambiar(p,tipo=tipo_destino)
    v=preview(org,[{'sku':p.sku,'tipo':tipo_destino}])
    assert v[0]['accion']=='rechazado' and 'SKU propios' in v[0]['errores'][0]
    assert ProductoFichaMaestra.query.filter_by(producto_id=p.id).one().tipo==tipo_origen


def test_combo_y_componente_tienen_sku_diferentes_sin_duplicar_componente(entorno):
    _,org,_,unidad=entorno
    preparar(db.engine)
    simple=crear(org,sku='ART-001')
    combo=crear(org,sku='COMBO-001',tipo='combo',componentes_combo=[{'sku':simple.sku,'cantidad':'3'}],unidad_combo_id=unidad.id)
    def perfil(p,tipo):
        return crear_o_actualizar_perfil(organizacion_id=org.id,unidad_negocio_id=unidad.id,producto_id=p.id,tipo=tipo,
            Producto=Producto,UnidadNegocio=UnidadNegocio,PerfilCosteoProducto=PerfilCosteoProducto,db_session=db.session)
    ps=perfil(simple,'simple');pc=perfil(combo,'combo')
    assert ComboProductoComponente.query.filter_by(combo_perfil_id=pc.id,componente_perfil_id=ps.id).one().cantidad == 3
    assert Producto.query.count()==2
    assert pc.producto.sku=='COMBO-001' and pc.componentes_combo[0].componente.producto.sku=='ART-001'


def test_no_stockeable_no_genera_otro_sku_desde_fuente_de_insumo(entorno):
    from services.materias_primas_inventario import preparar_materia_prima
    _,org,_,unidad=entorno
    preparar(db.engine)
    insumo=InsumoProductivo(organizacion_id=org.id,codigo='FUENTE-NS',nombre='Artículo',tipo='consumible',unidad_medida='unidad',activo=True)
    db.session.add(insumo);db.session.commit()
    crear(org,no_stockeable=True,insumo_id=insumo.id,permite_correo=False,permite_via_cargo=False)
    with pytest.raises(ValueError,match='No stockeable'):
        preparar_materia_prima(insumo=insumo,sku='DUP-NS',organizacion_id=org.id,unidad_negocio_id=unidad.id,Producto=Producto,ItemInventario=None,db_session=db.session)
    assert Producto.query.count()==1


def test_stock_negativo_manual_lote_y_opciones_incompatibles(entorno):
    _, org, _, _ = entorno
    preparar(db.engine)
    p = crear(org)
    assert not ProductoFichaMaestra.query.one().permitir_stock_negativo
    cambiar(p, permitir_stock_negativo=True)
    assert ProductoFichaMaestra.query.one().permitir_stock_negativo
    v = preview(org, [{'sku': p.sku, 'nombre': 'Nuevo nombre'}]); aplicar(org, v)
    assert ProductoFichaMaestra.query.one().permitir_stock_negativo
    v = preview(org, [{'sku': p.sku, 'permitir_stock_negativo': 'No'}]); aplicar(org, v)
    assert not ProductoFichaMaestra.query.one().permitir_stock_negativo
    with pytest.raises(ValueError, match='incompatibles'):
        cambiar(p, no_stockeable=True, permitir_stock_negativo=True, permite_correo=False)
    assert not ProductoFichaMaestra.query.one().no_stockeable
    assert 'permitir_stock_negativo' in plantilla_csv().splitlines()[0]


def test_guardias_anteriores_continuan_antes_de_migrar_columna_negativo(entorno):
    from sqlalchemy import text
    from scripts.preparar_ficha_productos import DDL
    from services.producto_habilitaciones import leer_ficha, esquema_ficha_disponible, exigir_producto_stockeable
    _, org, _, _ = entorno
    p = Producto(organizacion_id=org.id, sku='ANTERIOR-NS', descripcion='Anterior')
    db.session.add(p); db.session.commit()
    with db.engine.begin() as c:
        c.execute(text(DDL.replace('permitir_stock_negativo BOOLEAN NOT NULL DEFAULT FALSE,', '')))
        c.execute(text("INSERT INTO producto_ficha_maestra (producto_id,organizacion_id,nombre,linea,unidad_medida,tipo,activo,no_stockeable,habilita_compra,habilita_venta,habilita_insumo,habilita_componente,revision) VALUES (:p,:o,'Anterior','','unidad','simple',1,1,1,0,1,0,1)"), {'p':p.id,'o':org.id})
    assert not esquema_ficha_disponible(db.session)
    assert not leer_ficha(p, db.session).permitir_stock_negativo
    with pytest.raises(ValueError, match='Disponible para venta'):
        exigir_uso_producto(p, 'venta', db.session)
    with pytest.raises(ValueError, match='No stockeable'):
        exigir_producto_stockeable(p, db.session)
    db.session.rollback()
    assert 'Permitir stock negativo' in preparar(db.engine)
    f = ProductoFichaMaestra.query.one()
    assert f.no_stockeable and not f.habilita_venta and not f.permitir_stock_negativo
    assert 'ya preparada' in preparar(db.engine)


def test_movimientos_usan_regla_maestra_y_no_permiten_desactivar_con_saldo_negativo(entorno):
    from models.inventario_saas import ItemInventario
    from models.existencia_sucursal import ExistenciaSucursal
    from models.sucursal_operativa import SucursalOperativa
    from models.movimiento_inventario import MovimientoInventario
    from services.inventario_nucleo import registrar_movimiento
    _, org, otra, _ = entorno
    preparar(db.engine)
    db.metadata.create_all(db.engine, tables=[SucursalOperativa.__table__, ItemInventario.__table__, ExistenciaSucursal.__table__, MovimientoInventario.__table__])
    p = crear(org)
    s = SucursalOperativa(organizacion_id=org.id, codigo='NEG', nombre='Prueba', activa=False)
    db.session.add(s); db.session.flush()
    e = ExistenciaSucursal(organizacion_id=org.id, producto_id=p.id, sucursal_operativa_id=s.id, stock_actual=0, stock_reservado=0, stock_bloqueado=0)
    db.session.add(e); db.session.commit()
    def mover(tipo, cantidad):
        return registrar_movimiento(e, tipo=tipo, cantidad=cantidad, motivo='UAT aislado', MovimientoInventario=MovimientoInventario, db_session=db.session)
    with pytest.raises(ValueError, match='suficiente'):
        mover('egreso', 2)
    assert e.stock_actual == 0 and MovimientoInventario.query.count() == 0
    cambiar(p, permitir_stock_negativo=True)
    movimiento = mover('egreso', 2)
    assert e.stock_actual == -2
    assert movimiento.stock_actual_anterior == 0 and movimiento.stock_actual_nuevo == -2
    with pytest.raises(ValueError, match='Regularizá'):
        cambiar(p, permitir_stock_negativo=False)
    v = preview(org, [{'sku':p.sku, 'permitir_stock_negativo':'No'}])
    assert v[0]['accion'] == 'rechazado'
    mover('ajuste', -1)
    assert e.stock_actual == -3
    with pytest.raises(ValueError, match='suficiente'):
        mover('reserva', 1)
    assert e.stock_reservado == 0
    mover('ingreso', 3)
    cambiar(p, permitir_stock_negativo=False)
    assert not ProductoFichaMaestra.query.one().permitir_stock_negativo and e.stock_actual == 0
    # Un permiso de otra organización no autoriza este producto.
    crear(otra, sku=p.sku, permitir_stock_negativo=True)
    with pytest.raises(ValueError, match='suficiente'):
        mover('egreso', 1)
    assert e.stock_actual == 0


def test_ruta_casilla_stock_negativo_guarda_y_reabre(entorno):
    app, org, _, _ = entorno
    preparar(db.engine)
    configurar_rutas(app, org)
    cliente = app.test_client()
    respuesta = cliente.post('/admin/productos', data=form_datos(permitir_stock_negativo=True), follow_redirects=True)
    assert respuesta.status_code == 200 and 'Permite stock negativo' in respuesta.text
    assert 'name="permitir_stock_negativo"' in respuesta.text
    p = Producto.query.one()
    assert ProductoFichaMaestra.query.one().permitir_stock_negativo
    _, filas = construir_filas([p], db.session, org.id)
    formulario = form_datos() | {'accion':'editar_producto', 'producto_id':p.id, 'huella':filas[0]['huella']}
    respuesta = cliente.post('/admin/productos', data=formulario, follow_redirects=True)
    assert respuesta.status_code == 200
    assert not ProductoFichaMaestra.query.one().permitir_stock_negativo
    assert Producto.query.count() == 1


@pytest.mark.parametrize('componentes', [None, [], [{'sku':'BASE','cantidad':'0'}], [{'sku':'BASE','cantidad':'-1'}], [{'sku':'BASE','cantidad':'NaN'}], [{'sku':'BASE','cantidad':'0.0000001'}], [{'sku':'BASE','cantidad':'1'},{'sku':'BASE','cantidad':'2'}], [{'sku':'COMBO-NUEVO','cantidad':'1'}], [{'sku':'NO-EXISTE','cantidad':'1'}]])
def test_combo_invalido_no_crea_producto_ficha_ni_perfiles(entorno, componentes):
    _, org, _, _ = entorno
    preparar(db.engine); crear(org, sku='BASE')
    extra = {} if componentes is None else {'componentes_combo':componentes}
    with pytest.raises(ValueError):
        crear(org, sku='COMBO-NUEVO', tipo='combo', **extra)
    assert Producto.query.count() == 1
    assert ProductoFichaMaestra.query.count() == 1
    assert PerfilCosteoProducto.query.count() == 0
    assert ComboProductoComponente.query.count() == 0


def test_combo_comparte_composicion_con_costos_y_preserva_otros_ambitos(entorno):
    _, org, _, unidad = entorno
    preparar(db.engine)
    a=crear(org,sku='PARTE-A');b=crear(org,sku='PARTE-B',tipo='produccion')
    c=crear(org,sku='COMBO',tipo='combo',componentes_combo=[{'sku':a.sku,'cantidad':'2'},{'sku':b.sku,'cantidad':'1.5'}])
    general=PerfilCosteoProducto.query.filter_by(producto_id=c.id,unidad_negocio_id=None).one()
    assert len(general.componentes_combo)==2 and PerfilCosteoProducto.query.count()==3
    antes=ComboProductoComponente.query.filter_by(combo_perfil_id=general.id).order_by(ComboProductoComponente.id).all()
    id_a=antes[0].id
    cambiar(c,componentes_combo=[{'sku':a.sku,'cantidad':'4'}])
    assert ComboProductoComponente.query.one().id==id_a
    assert ComboProductoComponente.query.one().cantidad==4
    cambiar(c,unidad_combo_id=unidad.id,componentes_combo=[{'sku':b.sku,'cantidad':'3'}])
    assert ComboProductoComponente.query.count()==2
    # General y la unidad son los perfiles originales de Costos, no otra receta.
    _,filas=construir_filas([c],db.session,org.id)
    assert len(filas[0]['composiciones'])==2
    assert filas[0]['datos']['componentes_combo']==[{'sku':a.sku,'cantidad':'4.000000'}]
    assert PerfilCosteoProducto.query.filter_by(producto_id=c.id).count()==2
    with pytest.raises(ValueError,match='no puede quedar vacío'):
        cambiar(c,componentes_combo=[])
    assert ComboProductoComponente.query.count()==2
    # Una modificación desde Costos invalida el formulario abierto del maestro.
    abierta=filas[0]
    linea=ComboProductoComponente.query.filter_by(combo_perfil_id=general.id).one()
    linea.cantidad=5;db.session.commit()
    with pytest.raises(ValueError,match='cambió'):
        guardar_ficha(abierta['datos'],Producto=Producto,db_session=db.session,organizacion_id=org.id,
            producto_id=c.id,huella_esperada=abierta['huella'])
    assert linea.cantidad==5


def test_combo_rechaza_componente_ajeno_no_habilitado_inactivo_y_otro_combo(entorno):
    _,org,otra,_=entorno
    preparar(db.engine)
    a=crear(org,sku='BASE');crear(otra,sku='AJENO')
    otro=crear(org,sku='OTRO-COMBO',tipo='combo',componentes_combo=[{'sku':a.sku,'cantidad':'1'}])
    for sku in ('AJENO',otro.sku):
        with pytest.raises(ValueError):
            crear(org,sku='INVALIDO',tipo='combo',componentes_combo=[{'sku':sku,'cantidad':'1'}])
    cambiar(a,habilita_componente=False)
    with pytest.raises(ValueError,match='Componente de combo'):
        crear(org,sku='INVALIDO',tipo='combo',componentes_combo=[{'sku':a.sku,'cantidad':'1'}])
    cambiar(a,habilita_componente=True,activo=False)
    with pytest.raises(ValueError,match='Componente de combo'):
        crear(org,sku='INVALIDO',tipo='combo',componentes_combo=[{'sku':a.sku,'cantidad':'1'}])
    assert Producto.query.filter_by(organizacion_id=org.id).count()==2


def test_lote_combo_obliga_composicion_previsualiza_y_guarda_atomico(entorno):
    _,org,_,_=entorno
    preparar(db.engine);crear(org,sku='BASE')
    entrada=datos(sku='COMBO-LOTE',tipo='combo')
    v=preview(org,[entrada])
    assert v[0]['accion']=='rechazado' and 'al menos un producto' in v[0]['errores'][0]
    with pytest.raises(ValueError,match='filas rechazadas'):
        aplicar(org,v)
    assert Producto.query.count()==1
    v=preview(org,[entrada|{'componentes_combo':'BASE=2'}]);aplicar(org,v)
    c=Producto.query.filter_by(sku='COMBO-LOTE').one()
    assert ComboProductoComponente.query.one().cantidad==2
    v=preview(org,[{'sku':c.sku,'nombre':'Nombre actualizado'}]);aplicar(org,v)
    assert ComboProductoComponente.query.count()==1
    assert ComboProductoComponente.query.one().cantidad==2
    v=preview(org,[{'sku':c.sku,'componentes_combo':'BASE=3'}]);aplicar(org,v)
    assert ComboProductoComponente.query.one().cantidad==3
    # Un fallo posterior de otra fila revierte también el combo del lote.
    v=preview(org,[datos(sku='COMBO-ATOMIC',tipo='combo')|{'componentes_combo':'BASE=1'},datos(sku='SEGUNDO')])
    crear(org,sku='SEGUNDO')
    with pytest.raises(ValueError):
        aplicar(org,v)
    assert Producto.query.filter_by(sku='COMBO-ATOMIC').count()==0
    assert PerfilCosteoProducto.query.filter_by(producto_id=c.id).count()==1
    assert ComboProductoComponente.query.count()==1


def test_ruta_combo_exige_componentes_y_restaura_datos_ante_error(entorno,monkeypatch):
    import json
    import services.productos_ficha_maestra as servicio
    app,org,_,_=entorno
    preparar(db.engine);crear(org,sku='BASE');configurar_rutas(app,org)
    cliente=app.test_client()
    formulario=form_datos(sku='COMBO-UI',tipo='combo')
    respuesta=cliente.post('/admin/productos',data=formulario,follow_redirects=True)
    assert respuesta.status_code==200 and 'Un combo no puede quedar vacío' in respuesta.text
    assert Producto.query.count()==1
    formulario['componentes_combo_json']=json.dumps([{'sku':'BASE','cantidad':'2'}])
    # Falla en la misma transacción luego de insertar maestro/ficha.
    guardar_original=servicio.guardar_composicion
    def fallar(*args): raise ValueError('Prueba de rollback completo')
    monkeypatch.setattr(servicio,'guardar_composicion',fallar)
    respuesta=cliente.post('/admin/productos',data=formulario)
    assert 'Prueba de rollback completo' in respuesta.text
    assert Producto.query.count()==1 and ProductoFichaMaestra.query.count()==1
    assert PerfilCosteoProducto.query.count()==0
    monkeypatch.setattr(servicio,'guardar_composicion',guardar_original)
    respuesta=cliente.post('/admin/productos',data=formulario,follow_redirects=True)
    assert respuesta.status_code==200 and 'ficha guardada correctamente' in respuesta.text
    assert Producto.query.count()==2 and ComboProductoComponente.query.one().cantidad==2
    assert 'Productos que componen el combo' in respuesta.text and 'Agregar componente' in respuesta.text


def test_descripcion_opcional_independiente_del_nombre(entorno):
    _,org,_,_=entorno;preparar(db.engine)
    p=crear(org,nombre='Producto con nombre',descripcion='')
    assert p.descripcion==''
    assert ProductoFichaMaestra.query.filter_by(producto_id=p.id).one().nombre=='Producto con nombre'
    cambiar(p,nombre='Nombre actualizado',descripcion='')
    assert p.descripcion==''
    cambiar(p,descripcion='Acero pintado, terminación mate.')
    cambiar(p,nombre='Otro nombre')
    assert p.descripcion=='Acero pintado, terminación mate.'
    cambiar(p,descripcion='')
    assert p.descripcion==''
    _,filas=construir_filas([p],db.session,org.id)
    assert filas[0]['datos']['descripcion']=='' and filas[0]['datos']['nombre']=='Otro nombre'


def test_lote_alta_sin_descripcion_no_copia_nombre(entorno):
    _,org,_,_=entorno;preparar(db.engine)
    d=datos('OPCIONAL-LOTE');d.pop('descripcion')
    v=preview(org,[d]);assert not v[0]['errores']
    aplicar(org,v)
    p=Producto.query.filter_by(sku='OPCIONAL-LOTE').one()
    assert p.descripcion==''
    aplicar(org,preview(org,[{'sku':p.sku,'nombre':'Nombre desde lote'}]))
    assert p.descripcion==''


def test_ruta_descripcion_opcional_alta_y_edicion(entorno):
    app,org,_,_=entorno;preparar(db.engine);configurar_rutas(app,org)
    cliente=app.test_client()
    r=cliente.post('/admin/productos',data=form_datos(sku='OPCIONAL-WEB',descripcion=''),follow_redirects=True)
    assert r.status_code==200
    p=Producto.query.filter_by(sku='OPCIONAL-WEB').one()
    assert p.descripcion=='' and 'Descripción (opcional)' in r.text
    assert 'se conserva el nombre como descripción' not in r.text
    _,filas=construir_filas([p],db.session,org.id)
    f=form_datos(sku=p.sku,nombre='Identificación propia',descripcion='Detalles del artículo')
    f.update(accion='editar_producto',producto_id=str(p.id),huella=filas[0]['huella'])
    assert cliente.post('/admin/productos',data=f).status_code==302
    assert p.descripcion=='Detalles del artículo'
    _,filas=construir_filas([p],db.session,org.id)
    f.update(huella=filas[0]['huella'],descripcion='')
    assert cliente.post('/admin/productos',data=f).status_code==302
    assert p.descripcion==''
    assert ProductoFichaMaestra.query.filter_by(producto_id=p.id).one().nombre=='Identificación propia'
