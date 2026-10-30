from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
import pytest
from werkzeug.datastructures import MultiDict
from extensions import db
from models.cotizaciones import CotizacionDolar as D,DesgasteLaserVersion as L
from models.fuentes_costo_productivo import MaquinaProductiva as M,MaquinaCostoVersion as V
from scripts.preparar_cotizaciones import preparar,TABLAS
from services import cotizaciones as s
from test_personal_admin import personal,entorno

@pytest.fixture
def cotizaciones(personal,monkeypatch):
    from modules.admin.cotizaciones import routes
    c,org,otra,u,modelos,mem=personal
    db.metadata.create_all(db.engine,tables=[M.__table__,V.__table__]);preparar(db.engine);preparar(db.engine)
    monkeypatch.setattr(routes,'resolver_tenant_usuario',lambda *a,**kw:mem)
    c.application.register_blueprint(routes.crear_blueprint_cotizaciones(dependencias=dict(db=db,UnidadNegocio=modelos['UnidadNegocio'],UsuarioOrganizacion=modelos['UsuarioOrganizacion'],usuario_actual=lambda:SimpleNamespace(id=1),login_required=lambda f:f,registrar_auditoria=lambda *a,**kw:None)))
    yield c,org,otra,u,mem
    db.session.rollback();db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS))+[V.__table__,M.__table__])

def dolar(valor='1500',version='',**kw):return MultiDict(dict(valor_dolar=valor,version_dolar=str(version),fecha_cotizacion=s.hoy().isoformat(),referencia='Referencia manual')|kw)

def laser(d,version='',**kw):
    r=MultiDict(dict(version_dolar=str(d),version_laser=str(version))|kw)
    for x in s.PREDETERMINADOS:r.add('consumible_usd',x['usd']);r.add('vida_horas',x['horas'])
    return r

def post(datos,accion,**campos):
    _,_,_,u,_=datos
    return MultiDict(dict(_csrf_token='csrf-personal',unidad_contexto_id=str(u.id),accion=accion)|campos)


def test_general_historia_y_dolar_obligatorio(cotizaciones):
    c,org,otra,u,_=cotizaciones
    assert s.actual(org.id,db.session) is None
    with pytest.raises(ValueError,match='dólar general'):s.guardar_laser(laser(''),org.id,u.id,1,db.session)
    d=s.guardar_dolar(dolar(),org.id,1,db.session);db.session.commit()
    assert d.valor_centavos==150000 and s.actual(otra.id,db.session) is None
    assert s.guardar_dolar(dolar(version=d.id),org.id,1,db.session).id==d.id
    nuevo=s.guardar_dolar(dolar('1600',d.id),org.id,1,db.session);db.session.commit()
    assert nuevo.numero_version==2 and D.query.count()==2 and not db.session.get(D,d.id).vigente
    with pytest.raises(ValueError,match='cambió'):s.guardar_dolar(dolar('1700',d.id),org.id,1,db.session)


def test_usd_comun_recalcula_sin_modificar_historia(cotizaciones):
    _,org,_,u,_=cotizaciones
    d=s.guardar_dolar(dolar(),org.id,1,db.session);db.session.commit()
    l=s.guardar_laser(laser(d.id),org.id,u.id,1,db.session);db.session.commit()
    m=db.session.get(M,l.maquina_id)
    assert m.activo and m.unidad_negocio_id==u.id and V.query.count()==0
    tarifa=s.tarifa_maquina(m)
    assert tarifa.costo_minuto_centavos==497 and tarifa.costo_hora_centavos==29813
    assert 'sin mano de obra' in tarifa.observacion and 'pendientes' in tarifa.observacion
    assert s.calcular(l,d).costo_minuto_centavos==497
    nuevo=s.guardar_dolar(dolar('2000',d.id),org.id,1,db.session);db.session.commit()
    assert s.tarifa_maquina(m).costo_minuto_centavos==663
    assert s.calcular(l,d).costo_minuto_centavos==497
    assert L.query.count()==1 and M.query.count()==1 and V.query.count()==0
    assert s.guardar_laser(laser(nuevo.id,l.id),org.id,u.id,1,db.session).id==l.id


def test_motor_usa_cotizacion_y_conserva_snapshot(cotizaciones):
    from services.composicion_costo_producto import construir_detalles
    _,org,_,u,_=cotizaciones
    d=s.guardar_dolar(dolar(),org.id,1,db.session);l=s.guardar_laser(laser(d.id),org.id,u.id,1,db.session);db.session.commit()
    m=db.session.get(M,l.maquina_id)
    perfil=SimpleNamespace(tipo='produccion',organizacion_id=org.id,unidad_negocio_id=u.id,insumos_costeo=[],operaciones_costeo=[],costos_fijos_costeo=[],maquinas_costeo=[SimpleNamespace(maquina=m,nombre='Cortar',minutos=Decimal('2'),orden=0,observacion=None)])
    antes=construir_detalles(perfil);assert antes[0]['costo_unitario_centavos']==497
    assert 'USD/ARS v1' in antes[0]['observacion']
    s.guardar_dolar(dolar('2000',d.id),org.id,1,db.session);db.session.commit()
    despues=construir_detalles(perfil)
    assert despues[0]['costo_unitario_centavos']==663 and 'USD/ARS v2' in despues[0]['observacion']
    assert antes[0]['costo_unitario_centavos']==497


def test_fechas_importes_y_revisiones_invalidas(cotizaciones):
    _,org,_,u,_=cotizaciones
    for valor in ('0','-1','NaN','inf','1.500','no'):
        with pytest.raises(ValueError):s.guardar_dolar(dolar(valor),org.id,1,db.session)
    for fecha in ('2026-02-30',(s.hoy()+timedelta(days=1)).isoformat()):
        with pytest.raises(ValueError):s.guardar_dolar(dolar(fecha_cotizacion=fecha),org.id,1,db.session)
    d=s.guardar_dolar(dolar(),org.id,1,db.session);db.session.commit()
    with pytest.raises(ValueError):s.guardar_dolar(dolar('2000',d.id,fecha_cotizacion=(s.hoy()-timedelta(days=1)).isoformat()),org.id,1,db.session)
    for vida in ('0','NaN','-3','0.0000001'):
        f=laser(d.id);f.setlist('vida_horas',[vida,'8000','8000'])
        with pytest.raises(ValueError):s.guardar_laser(f,org.id,u.id,1,db.session)
    assert L.query.count()==M.query.count()==0


def test_unidades_comparten_dolar_pero_no_configuracion(cotizaciones):
    from models.unidad_negocio import UnidadNegocio as U
    _,org,otra,u,_=cotizaciones
    b=U(organizacion_id=org.id,codigo='otra-unidad',nombre='Otra',activa=True);db.session.add(b);db.session.commit()
    d=s.guardar_dolar(dolar(),org.id,1,db.session);db.session.commit()
    uno=s.guardar_laser(laser(d.id),org.id,u.id,1,db.session);dos=s.guardar_laser(laser(d.id),org.id,b.id,1,db.session);db.session.commit()
    assert uno.maquina_id!=dos.maquina_id and s.configuracion(org.id,b.id,db.session).id==dos.id
    with pytest.raises(ValueError):s.guardar_laser(laser(d.id),otra.id,u.id,1,db.session)
    assert s.configuracion(otra.id,u.id,db.session) is None


def test_http_roles_csrf_cancelar_y_contexto(cotizaciones):
    c,org,_,u,mem=cotizaciones
    r=c.get('/admin/cotizaciones');assert r.status_code==200 and 'Sin cotización' in r.text
    assert D.query.count()==L.query.count()==M.query.count()==0
    f=post(cotizaciones,'guardar_dolar',**dict(dolar()))
    sincsrf=MultiDict(f);sincsrf.pop('_csrf_token')
    assert c.post('/admin/cotizaciones',data=sincsrf).status_code==400
    f['unidad_contexto_id']='999';assert c.post('/admin/cotizaciones',data=f).status_code in (302,400)
    f['unidad_contexto_id']=str(u.id)
    r=c.post('/admin/cotizaciones',data=f);assert r.status_code==302
    d=D.query.one();f=post(cotizaciones,'guardar_laser');f.update(laser(d.id))
    r=c.post('/admin/cotizaciones',data=f);assert r.status_code==302,r.text
    r=c.get('/admin/cotizaciones');assert r.status_code==200 and '4,97' in r.text
    assert r.text.count('<form')==r.text.count('</form>')
    assert 'cotizacion-historial' in r.text and 'cotizacion-confirmar' in r.text
    mem.rol='carga'
    assert c.get('/admin/cotizaciones').status_code==302
    assert c.post('/admin/cotizaciones',data=post(cotizaciones,'guardar_dolar',**dict(dolar('999',d.id)))).status_code==302
    assert D.query.count()==1


def test_versiones_configuracion_y_tarifa_manual_protegida(cotizaciones):
    from services.maquinas_productivas_db import registrar_costo_maquina
    _,org,_,u,_=cotizaciones
    d=s.guardar_dolar(dolar(),org.id,1,db.session);a=s.guardar_laser(laser(d.id),org.id,u.id,1,db.session);db.session.commit()
    f=laser(d.id,a.id);f.setlist('consumible_usd',['1800','20','70'])
    b=s.guardar_laser(f,org.id,u.id,1,db.session);db.session.commit()
    assert b.numero_version==2 and b.maquina_id==a.maquina_id and not db.session.get(L,a.id).vigente
    assert s.calcular(a,d).costo_minuto_centavos==497 and s.calcular(b,d).costo_minuto_centavos==591
    with pytest.raises(ValueError,match='cambió'):s.guardar_laser(laser(d.id,a.id),org.id,u.id,1,db.session)
    with pytest.raises(ValueError,match='dólar general'):
        registrar_costo_maquina(db.session.get(M,b.maquina_id),moneda='ARS',valor_adquisicion_centavos=100,vida_util_horas=1,horas_productivas_mensuales=1,MaquinaCostoVersion=V,db_session=db.session)
    assert V.query.count()==0


def test_modulo_sin_preparar_y_error_reabre_sin_guardar(cotizaciones):
    c,org,_,u,_=cotizaciones
    r=c.post('/admin/cotizaciones',data=post(cotizaciones,'guardar_dolar',**dict(dolar('0'))))
    assert r.status_code==400 and 'data-cotizacion-auto' in r.text and D.query.count()==0
    db.metadata.drop_all(db.engine,tables=list(reversed(TABLAS)))
    r=c.get('/admin/cotizaciones');assert r.status_code==200 and 'Falta preparar' in r.text
    r=c.post('/admin/cotizaciones',data=post(cotizaciones,'guardar_dolar',**dict(dolar())))
    assert r.status_code==400 and 'Falta preparar' in r.text


def test_preparacion_aislada_sin_importar_app(tmp_path):
    import os,subprocess,sys
    from sqlalchemy import create_engine,text
    ruta=tmp_path/'base.db';e=create_engine('sqlite:///'+str(ruta))
    with e.begin() as conn:
        for nombre in ['organizacion','unidad_negocio','maquina_productiva']:conn.execute(text('CREATE TABLE '+nombre+' (id INTEGER PRIMARY KEY)'))
    e.dispose()
    env=os.environ|dict(DATABASE_URL='sqlite:///'+str(ruta),MODO_LABORATORIO_DESCONECTADO='true',RENDER_GIT_BRANCH='integracion-saas-2026-09',RENDER_EXTERNAL_URL='https://staging.example')
    for _ in range(2):
        r=subprocess.run([sys.executable,'-m','scripts.preparar_cotizaciones','--staging'],env=env,capture_output=True,text=True)
        assert r.returncode==0,r.stderr
    env['MODO_LABORATORIO_DESCONECTADO']='false'
    r=subprocess.run([sys.executable,'-m','scripts.preparar_cotizaciones','--staging'],env=env,capture_output=True,text=True)
    assert r.returncode!=0


def test_cada_consumible_respeta_su_vida_util_sin_promediar():
    config=SimpleNamespace(id=1,numero_version=1,consumibles=[dict(usd_centavos=10000,horas='1000'),dict(usd_centavos=2000,horas='500'),dict(usd_centavos=7000,horas='1000')])
    d=SimpleNamespace(id=1,numero_version=1,fecha_cotizacion=s.hoy(),valor_centavos=10000)
    tarifa=s.calcular(config,d)
    assert tarifa.costo_hora_centavos==2100 and tarifa.costo_minuto_centavos==35
