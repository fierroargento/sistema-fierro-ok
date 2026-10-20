"""El borrador duplicado usa el alta normal con identidad y fotos propias."""
import json
from io import BytesIO
from werkzeug.datastructures import FileStorage

from extensions import db
from models.producto import Producto
from models.producto_datos_generales import ProductoImagenMaestra, ProductoCodigoBarras
from models.costo_producto_version import CostoProductoVersion
from models.perfil_costeo_producto import PerfilCosteoProducto
from services.productos_ficha_maestra import construir_filas
from test_producto_ficha_maestra import entorno, configurar_rutas, form_datos
from test_producto_datos_generales import completo, formulario, imagen
from test_producto_fabricacion_maestro import fabricacion
from test_producto_despiece import despiece, form_pp


def test_alta_desde_copia_con_foto_y_costo_propios_preserva_original(completo):
    app,org,_,_,proveedor,*_=completo
    configurar_rutas(app,org)
    cliente=app.test_client()
    base=form_datos(sku='ORIGINAL') | formulario(costo_maestro_presentado='1',precio_costo='123.45',moneda_costo='USD',iva_pct='21',proveedores_json=json.dumps([{'proveedor_id':proveedor.id,'codigo':'EXTERNO'}]),codigos_barras_json='["7790000000001"]').to_dict()
    assert cliente.post('/admin/productos',data=base|{'imagenes_producto':imagen()}).status_code==302
    original=Producto.query.one()
    _,filas=construir_filas([original],db.session,org.id);antes=filas[0]['huella']
    foto=ProductoImagenMaestra.query.one();foto_id=foto.id
    respuesta=cliente.get(f'/admin/productos/{original.id}/imagenes/{foto.id}')
    assert respuesta.status_code==200
    costo=CostoProductoVersion.query.one();estado=(costo.id,costo.estado,costo.vigente)
    copia=base|dict(sku='NUEVO',nombre='Producto adaptado',producto_id='',huella='nuevo',insumo_id='',proveedores_json=json.dumps([{'proveedor_id':proveedor.id,'codigo':''}]),codigos_barras_json='[]',imagen_principal='nueva:0')
    copia['imagenes_producto']=FileStorage(BytesIO(respuesta.data),filename='foto.png',content_type='image/png')
    assert cliente.post('/admin/productos',data=copia).status_code==302
    nuevo=Producto.query.filter_by(sku='NUEVO').one()
    foto_nueva=ProductoImagenMaestra.query.filter_by(producto_id=nuevo.id).one()
    assert nuevo.id!=original.id and foto_nueva.id!=foto_id
    assert foto_nueva.contenido==foto.contenido and foto_nueva.principal
    assert ProductoCodigoBarras.query.filter_by(producto_id=nuevo.id).count()==0
    costo_nuevo=CostoProductoVersion.query.filter_by(producto_id=nuevo.id).one()
    assert costo_nuevo.id!=costo.id and costo_nuevo.moneda=='USD' and costo_nuevo.costo_total_centavos==12345
    assert not costo_nuevo.vigente
    _,filas=construir_filas([original],db.session,org.id)
    assert filas[0]['huella']==antes
    assert (costo.id,costo.estado,costo.vigente)==estado


def test_copia_fabricacion_con_sku_propio_no_comparte_perfil_ni_despiece(despiece):
    f,_=despiece;app,org,*_=f
    cliente=app.test_client();base=form_pp(despiece)
    assert cliente.post('/admin/productos',data=base).status_code==302
    original=Producto.query.one();perfil=PerfilCosteoProducto.query.filter_by(producto_id=original.id).one()
    _,filas=construir_filas([original],db.session,org.id);antes=filas[0]['huella']
    plan=json.loads(base['produccion_json']);plan['piezas'][0]['cantidad']='30'
    copia=base|dict(sku='PP-COPIA',producto_id='',huella='nuevo',produccion_json=json.dumps(plan),produccion_huella='')
    assert cliente.post('/admin/productos',data=copia).status_code==302
    nuevo=Producto.query.filter_by(sku='PP-COPIA').one()
    perfil_nuevo=PerfilCosteoProducto.query.filter_by(producto_id=nuevo.id).one()
    assert perfil_nuevo.id!=perfil.id
    _,filas=construir_filas([original,nuevo],db.session,org.id)
    por_id={r['id']:r for r in filas}
    assert por_id[original.id]['huella']==antes
    fisico=por_id[nuevo.id]['producciones'][0]['despiece']['datos']
    assert fisico['piezas'][0]['cantidad']=='30'
    assert len(fisico['piezas'])==7 and len(fisico['tareas'])==13
