"""Normalización común: texto descriptivo, CUIT y teléfono, con excepciones técnicas."""
import pytest
from flask import Flask,request,jsonify
from pathlib import Path
from werkzeug.datastructures import MultiDict
from services.normalizacion_datos_formulario import normalizar,telefono,fiscal,registrar

@pytest.mark.parametrize('valor,esperado',[
 ('2920123456','5492920123456'),('+549 2920123456','5492920123456'),('54 2920 123456','5492920123456'),
 ('02920 15 123456','5492920123456'),('011 15 5734-7193','5491157347193'),('15 2920 123456','5492920123456'),
 ('0054 9 2920 123456','5492920123456'),('+54 9 011 15 5734 7193','5491157347193'),
 ('',''),('+1 202 555 0123','+12025550123')])
def test_telefonos_completos(valor,esperado):assert telefono(valor)==esperado

@pytest.mark.parametrize('valor',['123456','2920 12345','tel 2920123456','29201234567890','+549292012345'])
def test_telefonos_incompletos_no_inventan_digitos(valor):
    with pytest.raises(ValueError):telefono(valor)

@pytest.mark.parametrize('valor',['30643146645','30-64314664-5',' 30 64314664 5 '])
def test_cuit_con_y_sin_guiones(valor):assert fiscal(valor)=='30643146645'

@pytest.mark.parametrize('valor',['3064314664','306431466455','CUIT30643146645'])
def test_fiscal_invalido_no_se_recorta(valor):
    with pytest.raises(ValueError):fiscal(valor)

def test_mayusculas_y_excepciones():
    assert normalizar('razon_social','Madergöld s.a.')=='MADERGÖLD S.A.'
    assert normalizar('observacion','línea 1\nmañana')=='LÍNEA 1\nMAÑANA'
    for clave in ['password','password_confirm','email','url','sku','codigo','_csrf_token','huella','accion','estado','tipo','items_json','selectivo_token']:
        assert normalizar(clave,'aBc-123')=='aBc-123'
    assert normalizar('documento','30-64314664-5')=='30643146645'
    assert normalizar('documento','12345678')=='12345678'

@pytest.fixture()
def app():
    app=Flask(__name__,template_folder=str(Path('templates').resolve()))
    app.secret_key='prueba';app.config['TESTING']=True
    registrar(app);registrar(app)
    @app.route('/guardar',methods=['POST'])
    @app.route('/api/datos',methods=['POST'])
    @app.route('/admin/integraciones/ml/webhook',methods=['POST'])
    def guardar():return jsonify(request.get_json() if request.is_json else {k:request.form.getlist(k) for k in request.form})
    return app

def test_formulario_no_depende_de_javascript_y_conserva_multivalores(app):
    c=app.test_client()
    r=c.post('/guardar',data=MultiDict([('nombre','josé'),('cuit','30-64314664-5'),('telefono','02920 15 123456'),('password','aBc'),('email','Yo@Ejemplo.COM'),('estado','activo'),('ids','1'),('ids','2'),('_csrf_token','AbC')]))
    assert r.status_code==200
    assert r.json['nombre']==['JOSÉ'] and r.json['cuit']==['30643146645'] and r.json['telefono']==['5492920123456']
    assert r.json['ids']==['1','2'] and r.json['password']==['aBc'] and r.json['_csrf_token']==['AbC'] and r.json['email']==['Yo@Ejemplo.COM']
    assert r.json['estado']==['activo']

def test_invalido_no_llega_a_la_accion(app):
    r=app.test_client().post('/guardar',data={'telefono':'123'},headers={'Accept':'application/json'})
    assert r.status_code==400 and 'característica' in r.json['error']

def test_no_reescribe_json_integraciones_ni_api(app):
    c=app.test_client()
    assert c.post('/guardar',json={'nombre':'Mi Nombre','telefono':'123'}).json['nombre']=='Mi Nombre'
    for url in ['/api/datos','/admin/integraciones/ml/webhook']:
        assert c.post(url,data={'nombre':'Mi Nombre','telefono':'123'}).json['nombre']==['Mi Nombre']


def test_direccion_financiera_no_es_domicilio(app):
    r=app.test_client().post('/guardar',data={'accion':'registrar_movimiento','direccion':'credito','detalle':'venta del día'})
    assert r.json['direccion']==['credito'] and r.json['detalle']==['VENTA DEL DÍA']


def test_guardado_real_personal_canonico(personal):
    from models.fuentes_costo_productivo import EmpleadoProductivo
    from models.personal_administrativo import PersonalDetalle
    from extensions import db
    from test_personal_admin import campos
    c,org,_,u,*_=personal
    registrar(c.application)
    r=c.post('/admin/personal',data=campos(unidad_negocio_id=str(u.id),nombre='josé pérez',datos_ampliados_presentados='1',telefono='02920 15 123456',cuil='20-12345678-6',domicilio='calle río negro 123',email='Ejemplo@Correo.COM'))
    assert r.status_code==302,r.text
    e=EmpleadoProductivo.query.filter_by(organizacion_id=org.id,codigo='leg-001').one()
    d=db.session.get(PersonalDetalle,e.id)
    assert e.nombre=='JOSÉ PÉREZ' and d.domicilio=='CALLE RÍO NEGRO 123'
    assert d.telefono=='5492920123456' and d.cuil=='20123456786' and d.email=='Ejemplo@Correo.COM'
    r=c.post('/admin/personal',data=campos(codigo='otro',unidad_negocio_id=str(u.id),telefono='123'))
    assert r.status_code==400 and 'No se guardaron cambios' in r.text
    assert EmpleadoProductivo.query.count()==1
    assert c.post('/admin/personal',data=campos(_csrf_token='')).status_code==400

# La prueba anterior reutiliza la base y el guardián CSRF reales sin iniciar app.py.
from test_personal_admin import personal
from test_producto_ficha_maestra import entorno
