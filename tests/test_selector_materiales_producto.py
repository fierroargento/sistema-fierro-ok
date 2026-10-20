import json
from types import SimpleNamespace

from extensions import db
from models.producto import Producto
from models.compras import ProveedorCompra
from models.fuentes_costo_productivo import InsumoProductivo, InsumoPrecioVersion
from models.producto_datos_generales import ProductoProveedor
from services.productos_ficha_maestra import guardar_ficha
from services.selector_materiales_producto import enriquecer_insumos
from test_producto_ficha_maestra import entorno, datos
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion


def recursos(*insumos):
    return [dict(id=i.id,codigo=i.codigo,nombre=i.nombre,unidad=i.unidad_medida,unidad_id=i.unidad_negocio_id,activo=i.activo) for i in insumos]


def test_busqueda_reutiliza_enlaces_reales_y_distingue_codigos_iguales(fabricacion):
    app, org, otra, unidad, i, *_ = fabricacion
    segundo = InsumoProductivo(organizacion_id=org.id,codigo='MAT-2',nombre='Otra materia',unidad_medida=i.unidad_medida,tipo='materia_prima',activo=True)
    db.session.add(segundo);db.session.flush()
    productos=[]
    for n, insumo in enumerate([i, segundo]):
        p=guardar_ficha(datos(sku=f'SKU-MAT-{n}', nombre=insumo.nombre, unidad_medida=insumo.unidad_medida, insumo_id=insumo.id),Producto=Producto,db_session=db.session,organizacion_id=org.id)
        proveedor=ProveedorCompra(organizacion_id=org.id,codigo=f'P-{n}',razon_social=f'Proveedor {n}')
        db.session.add(proveedor);db.session.flush()
        db.session.add(ProductoProveedor(organizacion_id=org.id,producto_id=p.id,proveedor_id=proveedor.id,codigo='IGUAL-123',codigo_clave='igual-123'))
        productos.append(p)
    db.session.commit()
    antes=(Producto.query.count(),InsumoProductivo.query.count(),InsumoPrecioVersion.query.count())
    base=recursos(i,segundo)
    resultado=enriquecer_insumos(base,db.session,org.id)
    assert resultado[0]['skus']==['SKU-MAT-0'] and resultado[1]['skus']==['SKU-MAT-1']
    assert resultado[0]['codigos_proveedor']==[{'codigo':'IGUAL-123','proveedor':'Proveedor 0'}]
    assert resultado[1]['codigos_proveedor']==[{'codigo':'IGUAL-123','proveedor':'Proveedor 1'}]
    assert base==recursos(i,segundo)  # Solo enriquece la presentación, no altera el origen.
    assert antes==(Producto.query.count(),InsumoProductivo.query.count(),InsumoPrecioVersion.query.count())
    html=app.test_client().get('/admin/productos').text
    payload=html.split('id="productos-fabricacion-recursos">',1)[1].split('</script>',1)[0]
    catalogo=json.loads(payload)['insumos']
    assert next(r for r in catalogo if r['id']==i.id)['skus']==['SKU-MAT-0']


def test_fuente_importada_sin_sku_no_inventa_identidad_ni_expone_otro_tenant(fabricacion):
    _, org, otra, unidad, i, _, _, _, ajeno = fabricacion
    version=InsumoPrecioVersion.query.filter_by(insumo_id=i.id,vigente=True).first()
    version.proveedor_referencia='Proveedor de la lista importada';db.session.commit()
    resultado=enriquecer_insumos(recursos(i,ajeno),db.session,org.id)
    assert len(resultado)==1 and resultado[0]['id']==i.id
    assert resultado[0]['skus']==[] and resultado[0]['codigos_proveedor']==[]
    assert resultado[0]['proveedores']==['Proveedor de la lista importada']
    assert resultado[0]['codigo']==i.codigo and resultado[0]['unidad']==i.unidad_medida
