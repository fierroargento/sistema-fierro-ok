"""El método de Componentes/Insumos/Tareas se prueba con PP6040H ficticio."""
import json
from decimal import Decimal
import pytest
from extensions import db
from models.producto import Producto
from models.producto_despiece_costeo import ProductoDespieceCosteo
from models.producto_datos_generales import ProductoDatosGenerales
from models.fuentes_costo_productivo import InsumoProductivo,InsumoPrecioVersion
from models.composicion_costo_producto import ProductoInsumoCosteo,ProductoOperacionCosteo
from models.costo_producto_version import CostoProductoVersion
from models.perfil_costeo_producto import PerfilCosteoProducto
from services.productos_ficha_maestra import construir_filas
from services.productos_produccion_maestro import preparar,calcular
from services.composicion_costo_producto import construir_detalles
from services.costos_productos import preparar_detalles
from services.motor_costeo_productos import huella_detalles
from scripts.preparar_despiece_productos import preparar as preparar_despiece
from test_producto_ficha_maestra import entorno
from test_producto_datos_generales import completo
from test_producto_fabricacion_maestro import fabricacion,alta


@pytest.fixture()
def despiece(fabricacion):
    preparar_despiece(db.engine)
    app,org,otra,unidad,i,e,m,c,ajeno=fabricacion
    i.nombre='Hierro liso 6 mm';i.unidad_medida='metro'
    fuentes=[i]
    for codigo,nombre,um in [('PL','Planchuela','metro'),('TU','Tuerca','unidad'),('BU','Bulón','unidad')]:
        r=InsumoProductivo(organizacion_id=org.id,codigo=codigo,nombre=nombre,unidad_medida=um,tipo='materia_prima',activo=True)
        db.session.add(r);db.session.flush();fuentes.append(r)
    db.session.commit()
    yield fabricacion,fuentes
    db.session.rollback();ProductoDespieceCosteo.__table__.drop(db.engine,checkfirst=True)


def pp6040(d):
    f,(hierro,planchuela,tuerca,bulon)=d
    piezas=[]
    for nombre,r,cantidad,medida in [('Varillas emparrillado',hierro,24,'39.5'),('Laterales',planchuela,4,'35.5'),('Patas',hierro,2,'59'),('Manijas',hierro,2,'16.5'),('Bisagras',planchuela,2,'3'),('Tuercas patas',tuerca,4,''),('Bulones bisagra',bulon,2,'')]:
        piezas.append({'insumo_id':r.id,'nombre':nombre,'cantidad':str(cantidad),'largo_cm':medida,'modo':'longitud' if medida else 'directo'})
    nombres=['Corte varillas','Corte laterales','Corte bisagras','Corte patas','Corte manijas','Doblado laterales','Doblado patas','Doblado manijas','Armado en matriz','Soldado','Ensamblado','Amolado','Terminado']
    return {'unidad_id':'','piezas':piezas,'tareas':[{'nombre':n,'segundos':str(t)} for n,t in zip(nombres,[72,26,51,6,6,34,19,9,200,315,300,88,30])],'tarifa_id':f[5].id,'maquinas':[],'fijos':[]}


def form_pp(d,**extra):
    return alta(d[0],sku='UAT-PP6040H',produccion_json=json.dumps(pp6040(d)),iibb_maestro_presentado='1',iibb_pct='3.5',**extra)


def test_pp6040_agrupa_piezas_sin_merma_y_tareas_por_unidad(despiece):
    f,fuentes=despiece;plan=preparar(pp6040(despiece),db.session,f[1].id)
    consumos={r['insumo_id']:r['cantidad'] for r in plan['lineas']['insumos']}
    assert [consumos[r.id] for r in fuentes]==[Decimal('10.99'),Decimal('1.48'),Decimal('4'),Decimal('2')]
    assert all(r['porcentaje_merma']==0 for r in plan['lineas']['insumos'])
    assert sum(Decimal(t['segundos']) for t in plan['despiece']['tareas'])==1156
    assert len(plan['lineas']['operaciones'])==13
    assert len({r['empleado_id'] for r in plan['lineas']['operaciones']})==1
    assert plan['despiece']['piezas'][0]['nombre']=='Varillas emparrillado'
    assert Producto.query.count()==0 and ProductoDespieceCosteo.query.count()==0


def test_guarda_medidas_y_tiempos_en_mismo_perfil_reabre_y_no_duplica(despiece):
    f,fuentes=despiece;app,org,*_=f
    # Tarifas ficticias de ensayo; se verifica el método, no los precios históricos del Excel.
    from datetime import datetime
    for n,r in enumerate(fuentes[1:]):
        db.session.add(InsumoPrecioVersion(insumo_id=r.id,moneda='ARS',numero_version=1,precio_unitario_centavos=1000*(n+1),vigente=True,vigente_desde=datetime(2026,1,1)))
    db.session.commit()
    cliente=app.test_client();form=form_pp(despiece)
    respuesta=cliente.post('/admin/productos/calcular-fabricacion',data=form)
    assert respuesta.status_code==200,respuesta.text
    sim=respuesta.get_json();assert sim['tiempo_segundos']=='1156' and len(sim['consumos'])==4
    assert Producto.query.count()==0
    form['produccion_huella']=sim['huella'];r=cliente.post('/admin/productos',data=form)
    assert r.status_code==302, r.text[r.text.find('alerta-error'):r.text.find('alerta-error')+300]
    p=Producto.query.one();perfil=PerfilCosteoProducto.query.one()
    assert ProductoDespieceCosteo.query.count()==1 and ProductoInsumoCosteo.query.count()==4 and ProductoOperacionCosteo.query.count()==13
    datos=ProductoDatosGenerales.query.one();assert datos.iva_pct==21 and datos.iibb_pct==Decimal('3.5')
    v=CostoProductoVersion.query.one();assert not v.vigente and v.tipo=='calculado'
    assert huella_detalles(preparar_detalles(construir_detalles(perfil)))==huella_detalles(v.detalles)
    _,filas=construir_filas([p],db.session,org.id);fila=filas[0];estado=fila['producciones'][0]['despiece']
    assert estado['actual'] and len(estado['datos']['piezas'])==7 and len(estado['datos']['tareas'])==13
    form.update(accion='editar_producto',producto_id=str(p.id),huella=fila['huella'],produccion_huella='')
    assert cliente.post('/admin/productos',data=form).status_code==302
    assert CostoProductoVersion.query.count()==1
    html=cliente.get(r.location).text
    assert 'IVA del producto (%)' in html and 'IIBB (%)' in html
    assert 'producto-pieza-dialog' in html and 'producto-tarea-dialog' in html


@pytest.mark.parametrize('campo,valor',[('largo_cm','0'),('cantidad','-1'),('modo','otro'),('insumo_id','99999')])
def test_rechazos_del_componente_sin_altas(despiece,campo,valor):
    f,_=despiece;datos=pp6040(despiece);datos['piezas'][0][campo]=valor
    r=f[0].test_client().post('/admin/productos',data=alta(f,produccion_json=json.dumps(datos)))
    assert r.status_code==200 and Producto.query.count()==0 and ProductoDespieceCosteo.query.count()==0


def test_rechaza_cm_en_insumo_por_unidad_y_tarifa_ajena(despiece):
    f,fuentes=despiece;d=pp6040(despiece);d['piezas'][0]['insumo_id']=fuentes[2].id
    with pytest.raises(ValueError,match='cotizado por metro'):preparar(d,db.session,f[1].id)
    d=pp6040(despiece);d['tarifa_id']=99999
    with pytest.raises(ValueError):preparar(d,db.session,f[1].id)


def test_rendimiento_no_se_confunde_con_bulto_compra(despiece):
    f,fuentes=despiece;d=pp6040(despiece)
    d['piezas']=[{'nombre':'Recorte','insumo_id':fuentes[2].id,'cantidad':'3','modo':'rendimiento','rendimiento':'12'}]
    plan=preparar(d,db.session,f[1].id)
    assert plan['lineas']['insumos'][0]['cantidad']==Decimal('.25')


def test_script_idempotente_y_preserva_ficha(despiece):
    f,_=despiece;antes=InsumoProductivo.query.count();preparar_despiece(db.engine);preparar_despiece(db.engine)
    assert InsumoProductivo.query.count()==antes and Producto.query.count()==0


@pytest.mark.parametrize('iibb',['-1','100','NaN','3.1234567'])
def test_iibb_invalido_no_guarda_producto(despiece,iibb):
    r=despiece[0][0].test_client().post('/admin/productos',data=form_pp(despiece)|{'iibb_pct':iibb})
    assert r.status_code==200 and Producto.query.count()==0


def test_edicion_desde_costos_no_usa_tiempos_fisicos_obsoletos(despiece):
    f,_=despiece;cliente=f[0].test_client()
    assert cliente.post('/admin/productos',data=form_pp(despiece)).status_code==302
    perfil=PerfilCosteoProducto.query.one()
    from services.productos_despiece import cargar
    assert cargar(perfil)['actual']
    operacion=perfil.operaciones_costeo[0];operacion.minutos=Decimal('5');db.session.commit()
    assert not cargar(perfil)['actual']
    # La representación física no sustituye una edición posterior de la composición.
    from services.productos_produccion_maestro import leer_producciones
    assert not leer_producciones([Producto.query.one()],db.session,f[1].id)[Producto.query.one().id][0]['despiece']['actual']


def test_formulario_anterior_conserva_iibb_y_cero_es_explicito(despiece):
    f,_=despiece;cliente=f[0].test_client();form=form_pp(despiece)
    assert cliente.post('/admin/productos',data=form).status_code==302
    p=Producto.query.one()
    def editar():
        _,filas=construir_filas([p],db.session,f[1].id)
        form.update(accion='editar_producto',producto_id=str(p.id),huella=filas[0]['huella'])
        return cliente.post('/admin/productos',data=form)
    form.pop('iibb_maestro_presentado');form['iibb_pct']=''
    assert editar().status_code==302
    assert ProductoDatosGenerales.query.one().iibb_pct==Decimal('3.5')
    form.update(iibb_maestro_presentado='1',iibb_pct='0')
    assert editar().status_code==302
    assert ProductoDatosGenerales.query.one().iibb_pct==0


def test_fallo_despues_de_despiece_revierte_todo(despiece,monkeypatch):
    import services.productos_despiece as servicio
    real=servicio.guardar
    def fallo(*args,**kwargs):
        real(*args,**kwargs)
        raise ValueError('Fallo de ensayo después de las piezas')
    monkeypatch.setattr(servicio,'guardar',fallo)
    r=despiece[0][0].test_client().post('/admin/productos',data=form_pp(despiece))
    assert r.status_code==200 and 'Fallo de ensayo' in r.text
    for modelo in (Producto,ProductoDespieceCosteo,PerfilCosteoProducto,ProductoDatosGenerales,ProductoInsumoCosteo,ProductoOperacionCosteo,CostoProductoVersion):
        assert modelo.query.count()==0


def test_script_ejecuta_aislado_sin_monolito_y_rechaza_produccion(despiece,tmp_path):
    import os,sqlite3,subprocess,sys
    archivo=tmp_path/'staging.sqlite'
    destino=sqlite3.connect(str(archivo));origen=db.engine.raw_connection()
    origen.driver_connection.backup(destino);origen.close();destino.close()
    env=dict(os.environ,DATABASE_URL='sqlite:///'+str(archivo),MODO_LABORATORIO_DESCONECTADO='true',RENDER_GIT_BRANCH='integracion-saas-2026-09',RENDER_EXTERNAL_URL='https://fierro-staging.onrender.com')
    orden=[sys.executable,'-m','scripts.preparar_despiece_productos','--staging']
    r=subprocess.run(orden,env=env,capture_output=True,text=True,timeout=20)
    assert r.returncode==0,r.stderr
    assert 'Datos existentes conservados' in r.stdout
    env['RENDER_GIT_BRANCH']='main'
    r=subprocess.run(orden,env=env,capture_output=True,text=True,timeout=20)
    assert r.returncode!=0 and 'no es integración' in r.stderr
