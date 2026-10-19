import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest
from flask import abort, request, session
import hmac

from services.archivo_rentabilidad_ml import analizar_archivo, MAX_ARCHIVO_BYTES
from services.escenarios_rentabilidad_ml import CUENTA_ENSAYO, ESCENARIOS, escenario_rentabilidad
from services.rentabilidad_ml_offline import analizar_rentabilidad
from test_rentabilidad_ml_routes import app, ingresar

CONTEXTO = dict(organizacion_id=1, unidad_negocio_id=3, cuenta_codigo=CUENTA_ENSAYO)


def documento(caso='simple'):
    return escenario_rentabilidad(caso, organizacion_id=1, unidad_negocio_id=3)[0]


def codificar(d):
    return json.dumps(d, ensure_ascii=False).encode()


def cargar(client, d):
    return client.post('/admin/comercial/rentabilidad-ml/archivo', data=codificar(d), content_type='application/json')


@pytest.mark.parametrize('caso', ESCENARIOS)
def test_archivo_recalcula_los_siete_casos_sin_modificar_entrada(caso):
    d = documento(caso); original = deepcopy(d)
    entrada, resultado = analizar_archivo(codificar(d), **CONTEXTO)
    assert d == original == entrada
    assert resultado == analizar_rentabilidad(d, **CONTEXTO)
    assert resultado['controles'] == dict(persistencia=False, conexiones_externas=0, stock=0, pagos=0, publicaciones=0)


def test_exportacion_no_confia_en_resultado_ni_meta_del_archivo():
    entrada, resultado = analizar_archivo(codificar({'entrada': documento(),
        'resultado': {'totales': {'resultado_centavos': 99999999}},
        'escenario': {'nombre': '<script>falso</script>', 'precio_objetivo_centavos': 1}}), **CONTEXTO)
    assert resultado['totales']['resultado_centavos'] == 320000
    assert entrada == documento()


@pytest.mark.parametrize('raw', [b'', b'no json', b'[]', b'null', b'\xff',
    b'{"version":1,"version":2}', b'{"entrada":null}', b'{"x":NaN}', b'{"x":Infinity}',
    b'['*1100 + b']'*1100, b' '* (MAX_ARCHIVO_BYTES+1)])
def test_rechaza_archivo_invalido(raw):
    with pytest.raises(ValueError): analizar_archivo(raw, **CONTEXTO)


@pytest.mark.parametrize('campo,valor', [('organizacion_id',2), ('unidad_negocio_id',4),
    ('cuenta_codigo','cuenta-real'), ('moneda','USD'), ('version',True), ('fecha_corte','sin zona')])
def test_no_reinterpreta_contexto_o_moneda(campo, valor):
    d=documento();d[campo]=valor
    with pytest.raises(ValueError): analizar_archivo(codificar(d), **CONTEXTO)


def test_tipo_anidado_invalido_no_produce_500():
    d=documento(); d['eventos'][0]['tipo'] = []
    with pytest.raises(ValueError, match='estructura'): analizar_archivo(codificar(d), **CONTEXTO)


def test_bom_y_origen_archivo_son_admitidos_sin_acreditar_fuente():
    d=documento();d['origen']='archivo_offline'
    _,r=analizar_archivo(b'\xef\xbb\xbf'+codificar(d), **CONTEXTO)
    assert r['origen']=='archivo_offline'


@pytest.mark.parametrize('caso', ESCENARIOS)
def test_ruta_archivo_render_y_exportacion_recalculada(app, caso):
    c=app.test_client();ingresar(c)
    r=cargar(c, {'entrada':documento(caso), 'resultado':{'falso':True}, 'escenario':{'nombre':'META FALSA'}})
    assert r.status_code==200
    assert 'Resultado de datos declarados' in r.text
    assert 'Descargar evidencia recalculada' in r.text
    assert 'META FALSA' not in r.text
    assert r.headers['Cache-Control']=='no-store'
    assert r.headers['X-Content-Type-Options']=='nosniff'
    from html.parser import HTMLParser
    class Extraer(HTMLParser):
        active=False
        text=''
        def handle_starttag(self, tag, attrs):
            if tag=='script' and dict(attrs).get('id')=='evidencia-archivo': self.active=True
        def handle_endtag(self, tag):
            if tag=='script': self.active=False
        def handle_data(self, data):
            if self.active: self.text+=data
    parser=Extraer();parser.feed(r.text)
    evidencia=json.loads(parser.text)
    assert evidencia['entrada']==documento(caso)
    assert evidencia['resultado']==analizar_rentabilidad(documento(caso), **CONTEXTO)
    assert evidencia['escenario']['precio_objetivo_centavos'] is None


def test_ruta_rechaza_contexto_archivo_y_escapa_textos(app):
    c=app.test_client();ingresar(c)
    d=documento();d['organizacion_id']=2
    r=cargar(c,d);assert r.status_code==400 and 'contexto activo' in r.text
    assert 'evidencia-archivo' not in r.text
    d=documento();d['referencia_venta']='</script><script>alert(1)</script>'
    r=cargar(c,d);assert r.status_code==200
    assert '</script><script>alert(1)</script>' not in r.text
    assert '\\u003c/script\\u003e' in r.text


def test_ruta_rol_sesion_y_metodos(app):
    c=app.test_client()
    assert cargar(c,documento()).status_code==302
    ingresar(c, uid=2);assert cargar(c,documento()).status_code==403
    ingresar(c, organizacion_id=2);assert cargar(c,documento()).status_code==403
    ingresar(c, unidad_negocio_id=4);assert cargar(c,documento()).status_code==302
    ingresar(c)
    assert c.get('/admin/comercial/rentabilidad-ml/archivo').status_code==405
    assert c.post('/admin/comercial/rentabilidad-ml/archivo', data={'archivo':'x.json'}).status_code==400
    assert c.post('/admin/comercial/rentabilidad-ml/archivo', data=b'x'*(MAX_ARCHIVO_BYTES+1),content_type='application/json').status_code==400


def test_archivo_usa_csrf_global_sin_exencion(app):
    # Copia AST de la función real, no un sustituto de su comportamiento.
    arbol=ast.parse(Path('app.py').read_text())
    funcion=next(n for n in arbol.body if isinstance(n,ast.FunctionDef) and n.name=='validar_csrf')
    funcion.decorator_list=[]
    modulo=ast.Module(body=[funcion],type_ignores=[])
    scope={'app':app,'session':session,'request':request,'hmac':hmac,'abort':abort}
    exec(compile(modulo,'app.py','exec'),scope)
    app.before_request(scope['validar_csrf']);app.config['TESTING']=False
    c=app.test_client();ingresar(c)
    with c.session_transaction() as s:s['_csrf_token']='test-token'
    r=cargar(c,documento());assert r.status_code==400
    r=c.post('/admin/comercial/rentabilidad-ml/archivo',data=codificar(documento()),content_type='application/json',headers={'X-CSRF-Token':'test-token'})
    assert r.status_code==200
