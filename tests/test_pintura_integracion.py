"""El consumo automático usa las mismas líneas y precios que los insumos."""
import pytest
from extensions import db
from models.fuentes_costo_productivo import InsumoProductivo
from services.productos_produccion_maestro import preparar
from test_producto_ficha_maestra import entorno
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion
from test_producto_despiece import despiece


def test_pintura_se_expande_sin_duplicarse_y_desmarcar_la_quita(despiece):
    f, fuentes = despiece
    metal = fuentes[0]
    metal.nombre='BARRA PLANCHUELA 3/4X 1/8'
    pintura=InsumoProductivo(organizacion_id=f[1].id,codigo='POLVO',nombre='Pintura en polvo',tipo='consumible',unidad_medida='kg',activo=True)
    db.session.add(pintura);db.session.flush()
    datos={'piezas':[{'insumo_id':metal.id,'nombre':'Gancho','modo':'longitud','cantidad':'3','largo_cm':'18'}],
           'pintura':{'activa':True,'insumo_id':pintura.id,'rendimiento_m2_kg':'10'}}
    plan=preparar(datos,db.session,f[1].id)
    assert len(plan['lineas']['insumos'])==2
    assert plan['despiece']['pintura']['consumo_kg']=='0.002437'
    assert preparar(datos,db.session,f[1].id)['despiece']==plan['despiece']
    datos['pintura']['activa']=False
    assert len(preparar(datos,db.session,f[1].id)['lineas']['insumos'])==1


def test_rechaza_pintura_ajena_y_carga_manual_duplicada(despiece):
    f, fuentes = despiece
    datos={'piezas':[{'insumo_id':fuentes[0].id,'nombre':'Metal','modo':'longitud','cantidad':'1','largo_cm':'10'}],
           'pintura':{'activa':True,'insumo_id':f[-1].id,'superficie_manual_m2':'1'}}
    with pytest.raises(ValueError):preparar(datos,db.session,f[1].id)
    pintura=InsumoProductivo(organizacion_id=f[1].id,codigo='POLVO',nombre='Pintura',tipo='consumible',unidad_medida='kg',activo=True)
    db.session.add(pintura);db.session.flush()
    datos['pintura']['insumo_id']=pintura.id
    datos['piezas'].append({'insumo_id':pintura.id,'nombre':'Polvo','modo':'directo','cantidad':'0.1'})
    with pytest.raises(ValueError,match='ya está cargada'):preparar(datos,db.session,f[1].id)
