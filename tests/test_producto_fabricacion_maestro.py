"""Fabricación construida en el alta, con las fuentes y tablas existentes."""
import json
from datetime import datetime
from decimal import Decimal
import pytest
from sqlalchemy import inspect
from extensions import db
from models.producto import Producto
from models.perfil_costeo_producto import PerfilCosteoProducto
from models.costo_producto_version import CostoProductoVersion
from models.fuentes_costo_productivo import (InsumoProductivo,InsumoPrecioVersion,EmpleadoProductivo,EmpleadoCostoVersion,
    MaquinaProductiva,MaquinaCostoVersion,CostoFijoProductivo,CostoFijoVersion)
from models.composicion_costo_producto import ProductoInsumoCosteo,ProductoOperacionCosteo,ProductoMaquinaCosteo,ProductoCostoFijoCosteo
from services.productos_produccion_maestro import modelos,preparar,calcular,leer_producciones
from services.productos_ficha_maestra import construir_filas
from test_producto_ficha_maestra import entorno,crear,configurar_rutas,form_datos
from test_producto_datos_generales import completo,formulario


@pytest.fixture()
def fabricacion(completo):
    anteriores=set(inspect(db.engine).get_table_names())
    tablas=list({t.name:t for t in modelos()[2]}.values())
    db.metadata.create_all(db.engine,tables=tablas)
    app,org,otra,unidad,*_=completo
    insumo=InsumoProductivo(organizacion_id=org.id,codigo='MDF',nombre='MDF',tipo='materia_prima',unidad_medida='m2',activo=True)
    empleado=EmpleadoProductivo(organizacion_id=org.id,codigo='CARP',nombre='Carpintería',sector='Taller',activo=True)
    maquina=MaquinaProductiva(organizacion_id=org.id,codigo='LASER',nombre='Láser',categoria='Corte',activo=True)
    fijo=CostoFijoProductivo(organizacion_id=org.id,codigo='ALQ',nombre='Alquiler',categoria='Taller',integra_costo_produccion=True,criterio_distribucion='porcentaje',activo=True)
    ajeno=InsumoProductivo(organizacion_id=otra.id,codigo='AJENO',nombre='Ajeno',tipo='materia_prima',unidad_medida='kg',activo=True)
    db.session.add_all([insumo,empleado,maquina,fijo,ajeno]);db.session.flush()
    fecha=datetime(2026,1,1)
    db.session.add_all([
      InsumoPrecioVersion(insumo_id=insumo.id,moneda='ARS',numero_version=1,precio_unitario_centavos=10000,vigente=True,vigente_desde=fecha),
      EmpleadoCostoVersion(empleado_id=empleado.id,moneda='ARS',numero_version=1,sueldo_base_centavos=100000,horas_mensuales=100,horas_productivas=100,costo_mensual_total_centavos=100000,costo_hora_productiva_centavos=1000,costo_minuto_productivo_centavos=50,vigente=True,vigente_desde=fecha),
      MaquinaCostoVersion(maquina_id=maquina.id,moneda='ARS',numero_version=1,valor_adquisicion_centavos=100000,vida_util_horas=1000,horas_productivas_mensuales=100,costo_hora_centavos=1200,costo_minuto_centavos=20,vigente=True,vigente_desde=fecha),
      CostoFijoVersion(costo_fijo_id=fijo.id,moneda='ARS',numero_version=1,importe_mensual_centavos=100000,vigente=True,vigente_desde=fecha),
    ]);db.session.commit()
    configurar_rutas(app,org)
    yield app,org,otra,unidad,insumo,empleado,maquina,fijo,ajeno
    db.session.rollback()
    db.metadata.drop_all(db.engine,tables=[t for t in reversed(tablas) if t.name not in anteriores])


def receta(f):
    _,_,_,_,i,e,m,c,_=f
    return {'unidad_id':'','insumos':[{'insumo_id':i.id,'cantidad':'2','porcentaje_merma':'10'}],
      'operaciones':[{'empleado_id':e.id,'nombre':'Armado','minutos':'5'}],
      'maquinas':[{'maquina_id':m.id,'nombre':'Corte','minutos':'3'}],
      'fijos':[{'costo_fijo_id':c.id,'porcentaje_asignacion':'20','unidades_mensuales':'100'}]}


def alta(f,**extra):
    return form_datos(sku='PRODUCIDO',tipo='produccion',descripcion='')|formulario(costo_maestro_presentado='1',precio_costo='',moneda_costo='ARS',iva_pct='21').to_dict()|{
      'produccion_presentada':'1','produccion_json':json.dumps(receta(f))}|extra


def test_calculo_usa_cuatro_fuentes_y_no_guarda(fabricacion):
    app,org,*_=fabricacion;cliente=app.test_client()
    r=cliente.post('/admin/productos/calcular-fabricacion',data=alta(fabricacion))
    assert r.status_code==200,r.text
    d=r.get_json()
    assert int(d['total_centavos'])==22510 # 22000 materiales+250 MO+60 máquina+200 indirectos
    assert d['moneda']=='ARS' and len(d['detalles'])==4
    assert Producto.query.count()==0 and PerfilCosteoProducto.query.count()==0 and CostoProductoVersion.query.count()==0
    assert cliente.post('/admin/productos/calcular-fabricacion',data=alta(fabricacion)|{'_csrf_token':''}).status_code==400


def test_alta_construye_y_reabre_misma_ficha_sin_duplicar(fabricacion):
    app,org,*_=fabricacion;cliente=app.test_client();form=alta(fabricacion)
    calculo=cliente.post('/admin/productos/calcular-fabricacion',data=form).get_json();form['produccion_huella']=calculo['huella']
    r=cliente.post('/admin/productos',data=form)
    assert r.status_code==302,r.text
    p=Producto.query.one();perfil=PerfilCosteoProducto.query.one();v=CostoProductoVersion.query.one()
    assert perfil.tipo=='produccion' and perfil.producto_id==p.id
    assert v.tipo=='calculado' and not v.vigente and v.estado=='preparatorio' and v.costo_total_centavos==22510
    assert [ProductoInsumoCosteo.query.count(),ProductoOperacionCosteo.query.count(),ProductoMaquinaCosteo.query.count(),ProductoCostoFijoCosteo.query.count()]==[1,1,1,1]
    _,filas=construir_filas([p],db.session,org.id);f=filas[0];d=f['producciones'][0]
    assert d['insumos'][0]['cantidad']=='2.000000' and d['operaciones'][0]['minutos']=='5.0000'
    form.update(accion='editar_producto',producto_id=str(p.id),huella=f['huella'],produccion_json=json.dumps(d),produccion_huella='')
    assert cliente.post('/admin/productos',data=form).status_code==302
    assert CostoProductoVersion.query.count()==1 and ProductoOperacionCosteo.query.count()==1
    assert 'producciones' in cliente.get(r.location).text


@pytest.mark.parametrize('cambio',['vacio','cantidad','minutos','merma','duplicado','ajeno','unidad','fila_ajena'])
def test_rechazos_no_dejan_altas_parciales(fabricacion,cambio):
    app,org,otra,unidad,i,e,m,c,ajeno=fabricacion;d=receta(fabricacion)
    if cambio=='vacio':d={}
    if cambio=='cantidad':d['insumos'][0]['cantidad']='0'
    if cambio=='minutos':d['operaciones'][0]['minutos']='-1'
    if cambio=='merma':d['insumos'][0]['porcentaje_merma']='101'
    if cambio=='duplicado':d['insumos']*=2
    if cambio=='ajeno':d['insumos'][0]['insumo_id']=ajeno.id
    if cambio=='unidad':d['unidad_id']='999999'
    if cambio=='fila_ajena':d['operaciones'][0]['id']='99999'
    form=alta(fabricacion,produccion_json=json.dumps(d))
    r=app.test_client().post('/admin/productos',data=form)
    assert r.status_code==200
    assert Producto.query.count()==0 and PerfilCosteoProducto.query.count()==0 and CostoProductoVersion.query.count()==0


def test_no_admite_importe_manual_produccion_y_combo(fabricacion):
    app,*_=fabricacion
    r=app.test_client().post('/admin/productos',data=alta(fabricacion,precio_costo='100'))
    assert r.status_code==200 and 'no se carga a mano' in r.text
    assert Producto.query.count()==0 and CostoProductoVersion.query.count()==0


def test_faltante_tarifa_pendiente_sin_costo_cero(fabricacion):
    app,*_=fabricacion;db.session.query(MaquinaCostoVersion).update({'vigente':False});db.session.commit()
    r=app.test_client().post('/admin/productos',data=alta(fabricacion))
    assert r.status_code==302
    assert 'costo pendiente' in app.test_client().get(r.location).text
    assert Producto.query.count()==1 and ProductoMaquinaCosteo.query.count()==1 and CostoProductoVersion.query.count()==0


def test_cambio_de_tarifas_despues_de_simular_rechaza_guardado(fabricacion):
    app,*_=fabricacion;cliente=app.test_client();form=alta(fabricacion)
    form['produccion_huella']=cliente.post('/admin/productos/calcular-fabricacion',data=form).get_json()['huella']
    db.session.query(InsumoPrecioVersion).update({'precio_unitario_centavos':20000});db.session.commit()
    r=cliente.post('/admin/productos',data=form)
    assert r.status_code==200 and 'costos cambiaron' in r.text
    assert Producto.query.count()==0 and ProductoInsumoCosteo.query.count()==0 and CostoProductoVersion.query.count()==0


def test_editar_otra_unidad_conserva_general_y_huella(fabricacion):
    app,org,_,unidad,*_=fabricacion;cliente=app.test_client();assert cliente.post('/admin/productos',data=alta(fabricacion)).status_code==302
    p=Producto.query.one();_,filas=construir_filas([p],db.session,org.id);vieja=filas[0]['huella']
    d=receta(fabricacion);d['unidad_id']=unidad.id;d['insumos'][0]['cantidad']='3'
    f=alta(fabricacion,accion='editar_producto',producto_id=str(p.id),huella=vieja,produccion_json=json.dumps(d))
    assert cliente.post('/admin/productos',data=f).status_code==302
    recetas=leer_producciones([p],db.session,org.id)[p.id]
    assert len(recetas)==2 and {r['insumos'][0]['cantidad'] for r in recetas}=={'2.000000','3.000000'}
    assert CostoProductoVersion.query.count()==2
    r=cliente.post('/admin/productos',data=f)
    assert r.status_code==200 and 'cambió' in r.text


def test_fallo_final_revierte_ficha_y_composicion(fabricacion,monkeypatch):
    import services.costos_productos as costos
    real=costos.crear_version_costo
    def fallo(**kw):real(**kw);raise ValueError('Fallo de prueba después del cálculo')
    monkeypatch.setattr(costos,'crear_version_costo',fallo)
    r=fabricacion[0].test_client().post('/admin/productos',data=alta(fabricacion))
    assert r.status_code==200 and 'Fallo de prueba' in r.text
    assert Producto.query.count()==0 and PerfilCosteoProducto.query.count()==0 and ProductoInsumoCosteo.query.count()==0 and CostoProductoVersion.query.count()==0


def test_combo_tampoco_admite_costo_manual(fabricacion):
    from test_producto_datos_generales import guardar as guardar_datos
    _,org,*_=fabricacion
    fuente=crear(org,sku='BASE-COMBO')
    combo=crear(org,sku='COMBO-PROPIO',tipo='combo',componentes_combo=[{'sku':fuente.sku,'cantidad':'2'}])
    with pytest.raises(ValueError,match='no se carga a mano'):
        guardar_datos(combo,formulario(costo_maestro_presentado='1',precio_costo='100',moneda_costo='ARS',iva_pct='21'))
    db.session.rollback()
    assert CostoProductoVersion.query.count()==0


def test_cambio_externo_de_composicion_invalida_formulario(fabricacion):
    app,org,*_=fabricacion;cliente=app.test_client();assert cliente.post('/admin/productos',data=alta(fabricacion)).status_code==302
    p=Producto.query.one();_,filas=construir_filas([p],db.session,org.id)
    f=alta(fabricacion,accion='editar_producto',producto_id=str(p.id),huella=filas[0]['huella'],produccion_json=json.dumps(filas[0]['producciones'][0]))
    linea=ProductoInsumoCosteo.query.one();linea.cantidad=4;db.session.commit()
    r=cliente.post('/admin/productos',data=f)
    assert r.status_code==200 and 'cambió' in r.text
    assert ProductoInsumoCosteo.query.one().cantidad==4


def test_costo_fijo_distribuido_exige_unidad_en_vez_de_error_tipo():
    from types import SimpleNamespace
    from services.composicion_costo_producto import _factor_productivo_unidad
    fijo=SimpleNamespace(nombre='Alquiler',distribuciones_versionadas=[SimpleNamespace(vigente=True,unidad_negocio_id=1,porcentaje_asignacion=100,porcentaje_productivo=100)])
    with pytest.raises(ValueError,match='unidad de fabricación'):
        _factor_productivo_unidad(fijo,None)
