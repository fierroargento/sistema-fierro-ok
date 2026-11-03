"""Repartos reales: fuente única, aislamiento, historial y costo por minutos."""
from decimal import Decimal
from types import SimpleNamespace
import pytest
from werkzeug.datastructures import MultiDict
from extensions import db
from models.unidad_negocio import UnidadNegocio
from models.fuentes_costo_productivo import CostoFijoDistribucionVersion,EmpleadoProductivo,CostoFijoProductivo
from models.reparto_gasto_sector import RepartoGastoSector as R
from scripts.preparar_reparto_sectores import preparar
from services import reparto_gasto_sector as s
from test_producto_ficha_maestra import entorno
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion,receta
from services.productos_produccion_maestro import preparar as preparar_plan,calcular
import json

@pytest.fixture
def reparto(fabricacion):
    app,org,otra,u,insumo,area,maquina,costo,ajeno=fabricacion
    db.metadata.create_all(db.engine,tables=[CostoFijoDistribucionVersion.__table__]);preparar(db.engine);preparar(db.engine)
    nautica=UnidadNegocio(organizacion_id=org.id,codigo='nautica',nombre='Náutica',activa=True)
    area.tipo_registro='recurso';area.unidad_negocio_id=u.id;costo.unidad_negocio_id=u.id
    db.session.add(nautica);db.session.commit()
    m=dict(UnidadNegocio=UnidadNegocio,EmpleadoProductivo=EmpleadoProductivo,CostoFijoDistribucionVersion=CostoFijoDistribucionVersion)
    yield fabricacion,nautica,m
    db.session.rollback();db.metadata.drop_all(db.engine,tables=[R.__table__,CostoFijoDistribucionVersion.__table__])

def form(u,area,otra,version=''):
    return MultiDict([('reparto_version',str(version)),('sector_unidad',str(u.id)),('sector_area',str(area.id)),('sector_porcentaje','60'),('sector_unidad',str(u.id)),('sector_area','deposito'),('sector_porcentaje','20'),('sector_unidad',str(otra.id)),('sector_area','deposito'),('sector_porcentaje','20')])

def guardar(r,datos=None):
    f,n,m=r;_,org,_,u,_,area,_,costo,_=f
    return s.guardar(costo,datos or form(u,area,n),org=org.id,unidad=u.id,session=db.session,modelos=m)

def test_guarda_reparte_preserva_responsable_y_no_duplica(reparto):
    f,n,m=reparto;_,org,_,u,_,area,_,costo,_=f
    r=guardar(reparto);db.session.commit()
    assert costo.unidad_negocio_id==u.id and len(costo.versiones)==1
    assert [Decimal(f['porcentaje']) for f in r.filas]==[60,20,20]
    ds=CostoFijoDistribucionVersion.query.filter_by(vigente=True).all()
    assert len(ds)==2
    fierro=next(d for d in ds if d.unidad_negocio_id==u.id)
    assert fierro.porcentaje_asignacion==80 and fierro.porcentaje_productivo==75
    assert guardar(reparto,form(u,area,n,r.id)).id==r.id
    with pytest.raises(ValueError,match='cambió'):guardar(reparto)
    assert len(s.actuales(db.session,org.id))==1

@pytest.mark.parametrize('campo,valor',[('sector_porcentaje','30'),('sector_porcentaje','NaN'),('sector_area','99999'),('sector_unidad','99999')])
def test_invalidos_no_escriben(reparto,campo,valor):
    f,n,m=reparto;_,_,_,u,_,area,*_=f
    d=form(u,area,n);vs=d.getlist(campo);vs[0]=valor;d.setlist(campo,vs)
    with pytest.raises(ValueError):guardar(reparto,d)
    assert R.query.count()==0 and CostoFijoDistribucionVersion.query.count()==0

def test_versionado_y_rollback(reparto):
    f,n,m=reparto;_,_,_,u,_,area,*_=f
    r=guardar(reparto);db.session.commit();d=form(u,area,n,r.id)
    d.setlist('sector_porcentaje',['50','30','20']);nuevo=guardar(reparto,d)
    assert nuevo.numero_revision==2
    db.session.rollback();assert R.query.count()==1 and R.query.one().vigente


def test_calculo_preview_integra_sector_sin_deposito_ni_doble_carga(reparto):
    f,n,m=reparto;_,org,_,u,_,area,_,costo,_=f
    guardar(reparto);db.session.commit()
    d=receta(f);d['unidad_id']=u.id;d['fijos']=[]
    resultado=calcular(preparar_plan(json.dumps(d),db.session,org.id),org.id)
    lineas=[x for x in resultado['detalles'] if x['codigo']==costo.codigo]
    assert len(lineas)==1
    # 100000 centavos * 60% / (100h *60) = 10 centavos/min, 5 minutos.
    assert lineas[0]['subtotal_centavos']==50
    assert 'Depósito excluido' in lineas[0]['observacion']
    d['fijos']=receta(f)['fijos']
    with pytest.raises(ValueError,match='duplicaciones'):calcular(preparar_plan(json.dumps(d),db.session,org.id),org.id)


def test_no_autoriza_otra_unidad(reparto):
    f,n,m=reparto;_,org,otra,u,_,area,_,costo,_=f
    with pytest.raises(ValueError,match='responsable'):s.guardar(costo,form(u,area,n),org=org.id,unidad=n.id,session=db.session,modelos=m)
    with pytest.raises(ValueError,match='responsable'):s.guardar(costo,form(u,area,n),org=otra.id,unidad=u.id,session=db.session,modelos=m)


def test_reparto_acordado_20_20_30_30(reparto):
    f,n,m=reparto;_,org,_,u,_,herreria,_,costo,_=f
    laser=EmpleadoProductivo(organizacion_id=org.id,unidad_negocio_id=u.id,codigo='laser-real',nombre='Láser',sector='Laser',puesto='Taller',tipo_registro='recurso',activo=True)
    nautico=EmpleadoProductivo(organizacion_id=org.id,unidad_negocio_id=n.id,codigo='nautico-real',nombre='Taller náutico',sector='Nautica',puesto='Taller',tipo_registro='recurso',activo=True)
    db.session.add_all([laser,nautico]);db.session.flush()
    d=MultiDict([('reparto_version','')])
    for unidad,area,pct in [(n.id,str(nautico.id),'20'),(u.id,'deposito','20'),(u.id,str(herreria.id),'30'),(u.id,str(laser.id),'30')]:
        d.add('sector_unidad',str(unidad));d.add('sector_area',area);d.add('sector_porcentaje',pct)
    guardar(reparto,d);db.session.commit()
    ds=CostoFijoDistribucionVersion.query.filter_by(vigente=True).all()
    fierro=next(x for x in ds if x.unidad_negocio_id==u.id)
    nautica=next(x for x in ds if x.unidad_negocio_id==n.id)
    assert (fierro.porcentaje_asignacion,fierro.porcentaje_productivo)==(80,75)
    assert (nautica.porcentaje_asignacion,nautica.porcentaje_productivo)==(20,100)
    assert costo.unidad_negocio_id==u.id
