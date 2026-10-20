"""Ficha de consulta real: fabricación, costos, permisos y ausencia de escrituras."""
from sqlalchemy import event

from extensions import db
from models.producto import Producto
from models.costo_producto_version import CostoProductoVersion
from models.producto_datos_generales import ProductoDatosGenerales
from services.producto_vista import obtener_vista, dinero, numero, fecha_local
from test_producto_ficha_maestra import entorno, crear, configurar_rutas
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion
from test_producto_despiece import despiece, form_pp


def test_ver_produccion_muestra_piezas_tareas_y_costo_preparatorio_sin_escribir(despiece):
    f, _ = despiece
    app, org, otra, *_ = f
    cliente=app.test_client()
    from datetime import datetime
    from models.fuentes_costo_productivo import InsumoPrecioVersion
    for n,insumo in enumerate(despiece[1][1:]):
        db.session.add(InsumoPrecioVersion(insumo_id=insumo.id,moneda='ARS',numero_version=1,precio_unitario_centavos=1000*(n+1),vigente=True,vigente_desde=datetime(2026,1,1)))
    db.session.commit()
    formulario=form_pp(despiece)
    calculo=cliente.post('/admin/productos/calcular-fabricacion',data=formulario)
    assert calculo.status_code==200,calculo.text
    formulario['produccion_huella']=calculo.json['huella']
    cliente.post('/admin/productos',data=formulario)
    producto=Producto.query.one()
    costo=CostoProductoVersion.query.one()
    antes=(Producto.query.count(),CostoProductoVersion.query.count(),costo.vigente,costo.estado)
    sentencias=[]
    def escuchar(conn,cursor,statement,parameters,context,executemany): sentencias.append(statement.strip().split()[0].upper())
    event.listen(db.engine,'before_cursor_execute',escuchar)
    try: respuesta=cliente.get(f'/admin/productos/{producto.id}/detalle')
    finally: event.remove(db.engine,'before_cursor_execute',escuchar)
    assert respuesta.status_code==200,respuesta.text
    html=respuesta.text
    for texto in ['De producción','Varillas emparrillado','Corte varillas','10,99','No vigente','preparatorio','IVA del producto','IIBB','Costos y precios','Imágenes y códigos','Canales']:
        assert texto in html
    assert html.count('data-vista-panel="')==7
    assert '<form' not in html and 'Guardar producto' not in html
    assert 'no-store' in respuesta.headers['Cache-Control']
    assert not set(sentencias)&{'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP'}
    assert antes==(Producto.query.count(),CostoProductoVersion.query.count(),costo.vigente,costo.estado)


def test_detalle_ajeno_no_se_expone_y_el_html_escapa_nombre(completo):
    app,org,otra,*_=completo
    configurar_rutas(app,org)
    propio=crear(org,sku='VISTA',nombre='<script>ataque()</script>',descripcion='Descripción opcional <b>texto</b>')
    ajeno=crear(otra,sku='AJENO',nombre='Nombre privado ajeno')
    cliente=app.test_client()
    respuesta=cliente.get(f'/admin/productos/{propio.id}/detalle')
    assert respuesta.status_code==200,respuesta.text
    assert '&lt;script&gt;ataque()&lt;/script&gt;' in respuesta.text
    assert '<script>ataque()' not in respuesta.text
    assert 'Nombre privado ajeno' not in respuesta.text
    assert cliente.get(f'/admin/productos/{ajeno.id}/detalle').status_code==404
    assert cliente.post(f'/admin/productos/{propio.id}/detalle',data={'_csrf_token':'csrf-test'}).status_code==405
    assert 'Sin versiones de costo guardadas' in respuesta.text
    assert 'Inventario aún no preparado' in respuesta.text
    assert 'data-vista-panel="composicion"' not in respuesta.text


def test_formato_no_convierte_vacio_en_cero_ni_cambia_moneda():
    assert dinero(None)=='—' and dinero(0)=='ARS 0,00'
    assert dinero(123456,'USD')=='USD 1.234,56'
    assert numero('0')=='0' and numero(None)=='—' and numero('10.990000')=='10,99'
    assert fecha_local('2026-10-20 20:00:00')=='20/10/2026 17:00'


def test_combo_conserva_su_identidad_y_muestra_composicion_existente(completo):
    app,org,*_=completo
    configurar_rutas(app,org)
    base=crear(org,sku='BASE-VISTA')
    combo=crear(org,sku='COMBO-VISTA',tipo='combo',componentes_combo=[{'sku':base.sku,'cantidad':'5'}])
    html=app.test_client().get(f'/admin/productos/{combo.id}/detalle').text
    assert 'COMBO-VISTA' in html and 'Composición del combo' in html
    assert '<td>BASE-VISTA</td><td>5</td>' in html
    assert 'Fabricación ·' not in html


def test_stock_listas_canales_y_observaciones_solo_del_producto_y_tenant(completo):
    from datetime import datetime
    from sqlalchemy import Table,Column,MetaData,Integer,String,DateTime
    from models.producto_datos_generales import ProductoProveedor, ProductoCodigoBarras
    app,org,otra,unidad,proveedor,*_=completo
    configurar_rutas(app,org)
    p=crear(org,sku='VISTA-DATOS');ajeno=crear(otra,sku='VISTA-AJENO')
    general=ProductoDatosGenerales(producto_id=p.id,organizacion_id=org.id,rubro='Herrería',subrubro='Parrillas',marca='Fierro',iva_pct=21,iibb_pct=3.5,utilidad_pct=50,utilidad_base='costo')
    db.session.add_all([general,ProductoProveedor(organizacion_id=org.id,producto_id=p.id,proveedor_id=proveedor.id,codigo='COD-EXTERNO'),ProductoCodigoBarras(organizacion_id=org.id,producto_id=p.id,codigo='7790000000001')]);db.session.commit()
    # Contratos físicos de los módulos opcionales; sin importar mappers ajenos al maestro.
    meta=MetaData()
    def tabla(nombre,enteros,textos,fechas=()):
        return Table(nombre,meta,*[Column(c,Integer) for c in enteros],*[Column(c,String) for c in textos],*[Column(c,DateTime) for c in fechas])
    cp=tabla('catalogo_producto',['id','organizacion_id','producto_id'],[])
    lp=tabla('lista_precio',['id','organizacion_id','unidad_negocio_id'],['nombre','moneda','estado'])
    li=tabla('lista_precio_item',['id','lista_precio_id','catalogo_producto_id','numero_version','costo_base_centavos','precio_elegido_centavos','impuestos_centavos','precio_final_centavos','margen_pct','impuesto_pct','vigente'],['estado'],['fecha_creacion'])
    ex=tabla('existencia_sucursal',['organizacion_id','producto_id','sucursal_operativa_id','stock_actual','stock_reservado','stock_bloqueado','stock_transito','stock_minimo','stock_maximo','control_activo'],[])
    v=tabla('vinculo_canal_comercial',['id','organizacion_id','unidad_negocio_id'],['nombre'])
    m=tabla('mapeo_publicacion_canal',['organizacion_id','vinculo_canal_comercial_id','catalogo_producto_id','identidad_verificada','permite_sincronizar'],['canal','publicacion_externa_id','variante_externa_id','sku_externo','estado'])
    o=tabla('observacion_comercial_canal',['organizacion_id','catalogo_producto_id','unidad_negocio_id','lista_precio_id','precio_publicado_centavos','comision_pct','cargo_fijo_centavos','costo_envio_centavos'],['tipo','cuenta_codigo','referencia_publicacion','origen'],['fecha_observacion'])
    meta.create_all(db.engine)
    try:
        db.session.execute(cp.insert(),[dict(id=1,organizacion_id=org.id,producto_id=p.id),dict(id=2,organizacion_id=otra.id,producto_id=ajeno.id)])
        db.session.execute(lp.insert(),[dict(id=1,organizacion_id=org.id,nombre='Lista UAT propia',moneda='ARS',estado='activo'),dict(id=2,organizacion_id=otra.id,nombre='SECRETO AJENO',moneda='USD',estado='activo')])
        precio=dict(numero_version=1,costo_base_centavos=10000,precio_elegido_centavos=15000,impuestos_centavos=3150,precio_final_centavos=18150,margen_pct=33,impuesto_pct=21,vigente=1,estado='vigente',fecha_creacion=datetime(2026,10,20,20,0))
        db.session.execute(li.insert(),[dict(precio,id=1,lista_precio_id=1,catalogo_producto_id=1),dict(precio,id=2,lista_precio_id=2,catalogo_producto_id=2)])
        sucursal=completo[6]
        db.session.execute(ex.insert(),dict(organizacion_id=org.id,producto_id=p.id,sucursal_operativa_id=sucursal.id,stock_actual=5,stock_reservado=1,stock_bloqueado=1,stock_transito=2,stock_minimo=0,control_activo=0))
        db.session.execute(v.insert(),[dict(id=1,organizacion_id=org.id,nombre='Cuenta UAT propia'),dict(id=2,organizacion_id=otra.id,nombre='CUENTA AJENA')])
        identidad=dict(canal='mercadolibre',variante_externa_id='',sku_externo='SKU-EXTERNO',estado='preparado_sin_conexion',identidad_verificada=0,permite_sincronizar=0)
        db.session.execute(m.insert(),[dict(identidad,organizacion_id=org.id,vinculo_canal_comercial_id=1,catalogo_producto_id=1,publicacion_externa_id='MLA-UAT-PROPIA'),dict(identidad,organizacion_id=org.id,vinculo_canal_comercial_id=2,catalogo_producto_id=1,publicacion_externa_id='NO-EXHIBIR-CRUZADA')])
        db.session.execute(o.insert(),dict(organizacion_id=org.id,catalogo_producto_id=1,unidad_negocio_id=unidad.id,lista_precio_id=1,tipo='mercadolibre',cuenta_codigo='Cuenta UAT',referencia_publicacion='OBS-UAT',precio_publicado_centavos=20000,comision_pct=14,cargo_fijo_centavos=100,costo_envio_centavos=1500,origen='importacion',fecha_observacion=datetime(2026,10,20,20,0)))
        db.session.commit()
        vista=obtener_vista(p,db.session,org.id)
        assert vista['stock'][0]['disponible']==3 and not vista['stock'][0]['control_activo']
        assert len(vista['precios'])==1 and vista['precios'][0]['precio_final_centavos']==18150
        assert len(vista['canales'])==1 and vista['canales'][0]['publicacion_externa_id']=='MLA-UAT-PROPIA'
        html=app.test_client().get(f'/admin/productos/{p.id}/detalle').text
        for valor in ['Lista UAT propia','ARS 181,50','Cuenta UAT propia','OBS-UAT','COD-EXTERNO','7790000000001','20/10/2026 17:00']:
            assert valor in html
        for valor in ['SECRETO AJENO','CUENTA AJENA','NO-EXHIBIR-CRUZADA']:
            assert valor not in html
    finally:
        db.session.rollback();meta.drop_all(db.engine)


def test_usuario_sin_rol_admin_no_puede_ver_detalle(completo,monkeypatch):
    from types import SimpleNamespace
    import modules.admin.productos.routes as rutas
    app,org,*_=completo;configurar_rutas(app,org)
    p=crear(org,sku='PRIVADO')
    monkeypatch.setattr(rutas,'resolver_tenant_usuario',lambda *a,**kw:SimpleNamespace(rol='carga',organizacion_id=org.id,organizacion=org))
    respuesta=app.test_client().get(f'/admin/productos/{p.id}/detalle')
    assert respuesta.status_code==302
    assert 'PRIVADO' not in respuesta.text
