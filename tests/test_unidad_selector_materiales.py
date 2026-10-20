"""Regresión: código proveedor importado en una unidad oculto desde General."""
import json
import re
import pytest

from extensions import db
from models.unidad_negocio import UnidadNegocio
from models.fuentes_costo_productivo import InsumoProductivo
from services.importacion_fuentes_costeo import previsualizar_fuentes, aplicar_fuentes
from services.productos_produccion_maestro import preparar
from test_producto_ficha_maestra import entorno
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion
from test_insumos_bultos import bultos


@pytest.fixture(autouse=True)
def habilitar_despiece(fabricacion):
    from scripts.preparar_despiece_productos import preparar as preparar_despiece
    from models.producto_despiece_costeo import ProductoDespieceCosteo
    preparar_despiece(db.engine)
    yield
    db.session.rollback()
    ProductoDespieceCosteo.__table__.drop(db.engine,checkfirst=True)


def inicial(html):
    return re.search(r'name="unidad_produccion_ui" data-unidad-inicial="([^"]*)"', html).group(1)


def test_codigo_21572_importado_es_visible_en_la_unidad_inicial_correcta(bultos):
    f, modelos, _ = bultos
    app, org, _, unidad, *_ = f
    mapeo = {str(n):campo for n,campo in enumerate(['codigo','nombre','tipo','unidad_medida','precio_unitario','proveedor'])}
    filas = [{'numero':2,'valores':['21572','Barra hierro liso 6 mm UAT','materia_prima','metro','100','Proveedor UAT']}]
    vista = previsualizar_fuentes('insumos',filas,mapeo,organizacion_id=org.id,unidad_negocio_id=unidad.id,modelos=modelos)
    aplicar_fuentes('insumos',vista,organizacion=org,unidad_activa=unidad,modelos=modelos,db_session=db.session,usuario=None)
    insumo = InsumoProductivo.query.filter_by(codigo='21572',organizacion_id=org.id).one()
    assert insumo.unidad_negocio_id == unidad.id
    cliente = app.test_client()
    with cliente.session_transaction() as sesion: sesion['unidad_negocio_id'] = unidad.id
    html = cliente.get('/admin/productos').text
    assert inicial(html) == str(unidad.id)
    datos = json.loads(html.split('id="productos-fabricacion-recursos">',1)[1].split('</script>',1)[0])
    recurso = next(r for r in datos['insumos'] if r['codigo']=='21572')
    assert recurso['unidad_id']==unidad.id and recurso['activo']
    receta = {'unidad_id':'','insumos':[{'insumo_id':insumo.id,'cantidad':'1','porcentaje_merma':'0'}]}
    with pytest.raises(ValueError): preparar(receta,db.session,org.id)
    receta['unidad_id']=str(unidad.id)
    plan = preparar(receta,db.session,org.id)
    assert plan['lineas']['insumos'][0]['insumo_id']==insumo.id


@pytest.mark.parametrize('seleccion', ['actual','segunda','ajena','inactiva'])
def test_default_usa_solo_unidades_activas_del_tenant(fabricacion,seleccion):
    app, org, otra, unidad, *_ = fabricacion
    segunda = UnidadNegocio(organizacion_id=org.id,codigo='dos',nombre='Segunda',activa=True)
    ajena = UnidadNegocio(organizacion_id=otra.id,codigo='ajena',nombre='Ajena',activa=True)
    inactiva = UnidadNegocio(organizacion_id=org.id,codigo='cerrada',nombre='Inactiva',activa=False)
    db.session.add_all([segunda,ajena,inactiva]);db.session.commit()
    elegida = {'actual':unidad,'segunda':segunda,'ajena':ajena,'inactiva':inactiva}[seleccion]
    cliente=app.test_client()
    with cliente.session_transaction() as sesion: sesion['unidad_negocio_id']=elegida.id
    assert inicial(cliente.get('/admin/productos').text)==(str(elegida.id) if seleccion in {'actual','segunda'} else '')
