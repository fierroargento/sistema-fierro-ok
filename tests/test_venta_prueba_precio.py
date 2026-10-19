"""Recorrido costo/embalaje -> previsión congelada -> resultado y relectura."""
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace as Obj

import pytest

from services.venta_prueba_precio import preparar_venta_prueba, _huella, CUENTA
from services.rentabilidad_ml_offline import analizar_rentabilidad
from services.archivo_rentabilidad_ml import analizar_archivo
from test_cobertura_precio_publicacion import fila, guardar
from test_enlace_economico_producto import fuentes, AHORA


def producto_uat():
    d = fuentes()
    c = d['costos'][0]
    c.costo_total_centavos = 493365
    c.detalles[0].cantidad = 1
    c.detalles[0].costo_unitario_centavos = 493365
    c.detalles[0].subtotal_centavos = 493365
    r = d['reglas_economicas'][0]
    r.impuesto_pct = 0
    r.incremento_redondeo_centavos = 100
    p = d['reglas_canal'][0]
    p.comision_pct = 10
    p.publicidad_pct = p.financiacion_pct = p.devoluciones_pct = 0
    p.umbral_envio_centavos = p.costo_envio_default_centavos = 0
    p.tramos = [Obj(precio_desde_centavos=0, precio_hasta_centavos=None, cargo_fijo_centavos=0)]
    guardar(fila(d), adicional_centavos=10000)
    return d


def analizar(d):
    return analizar_rentabilidad(d, organizacion_id=1, unidad_negocio_id=2, cuenta_codigo=CUENTA)


def documento(caso='previsto'):
    return preparar_venta_prueba(fila(producto_uat()), caso=caso, ahora=AHORA)


def test_fuentes_reales_del_producto_ensayo_y_embalaje_se_reutilizan_sin_escritura():
    datos = producto_uat()
    f = fila(datos)
    antes = deepcopy(f)
    d = preparar_venta_prueba(f, ahora=AHORA)
    r = analizar(d)
    assert d['lineas'][0]['precio_unitario_centavos'] == 669000
    assert d['lineas'][0]['costo_snapshot']['unitario_centavos'] == 493365
    assert d['lineas'][0]['previsto']['liquidacion_centavos'] == 602100
    assert d['gastos_locales_previstos_centavos'] == 10000
    assert r['enlace_precio']['neto_minimo_centavos'] == 592100
    assert r['enlace_precio']['neto_previsto_centavos'] == r['enlace_precio']['neto_ensayo_centavos'] == 592100
    assert r['enlace_precio']['estado'] == 'cubre_minimo'
    assert r['totales']['resultado_previsto_centavos'] == r['totales']['resultado_centavos'] == 98735
    assert r['totales']['diferencia_resultado_centavos'] == 0
    assert r['liquidacion']['observada_centavos'] == 602100
    assert r['liquidacion']['diferencia_detalle_centavos'] == 0
    assert r['estado'] == 'parcial' and 'impuestos' in r['faltantes']
    assert not r['enlace_precio']['definitivo'] and not r['enlace_precio']['publicacion_habilitada']
    assert f['inclusion'].canales_json == antes['inclusion'].canales_json
    assert f['trazabilidad_economica'] == antes['trazabilidad_economica']
    assert f['costo'].costo_total_centavos == 493365
    assert r['controles'] == {'persistencia':False, 'conexiones_externas':0, 'stock':0, 'pagos':0, 'publicaciones':0}


def test_envio_mayor_no_recalcula_prevision_para_ocultar_la_perdida():
    d = documento('envio_mayor')
    r = analizar(d)
    enlace = r['enlace_precio']
    assert enlace['neto_ensayo_centavos'] == 542100
    assert enlace['neto_previsto_centavos'] == 592100
    assert enlace['diferencia_previsto_centavos'] == enlace['diferencia_minimo_centavos'] == -50000
    assert enlace['estado'] == 'bajo_minimo'
    assert r['totales']['diferencia_resultado_centavos'] == -50000
    assert r['liquidacion']['diferencia_detalle_centavos'] == 0


@pytest.mark.parametrize('modo', ['incluido', 'sin_costo'])
def test_embalaje_incluido_o_sin_costo_no_se_descuenta_otra_vez(modo):
    datos = producto_uat()
    guardar(fila(datos), modo_embalaje=modo, adicional_centavos=0,
        detalle_ids=[11] if modo == 'incluido' else [])
    d = preparar_venta_prueba(fila(datos), ahora=AHORA)
    r = analizar(d)
    assert d['gastos_locales_previstos_centavos'] == 0
    assert d['lineas'][0]['precio_unitario_centavos'] == 657900
    assert r['enlace_precio']['neto_ensayo_centavos'] == 592110
    assert r['totales']['diferencia_resultado_centavos'] == 0
    assert d['lineas'][0]['costo_snapshot']['incluye_embalaje'] == (modo == 'incluido')


def test_releer_exportacion_ignora_resultado_y_no_usa_costo_actual():
    datos = producto_uat()
    d = preparar_venta_prueba(fila(datos), caso='envio_mayor', ahora=AHORA)
    anterior = analizar(d)
    datos['costos'][0].costo_total_centavos = 9999999
    datos['reglas_canal'][0].comision_pct = 90
    paquete = {'entrada':d, 'resultado':{'estado':'todo_bien', 'totales':{}}, 'escenario':{'falso':True}}
    entrada, r = analizar_archivo(json.dumps(paquete).encode(), organizacion_id=1,
        unidad_negocio_id=2, cuenta_codigo=CUENTA)
    assert r == anterior
    assert entrada == d and r['totales']['costo_centavos'] == 493365


@pytest.mark.parametrize('cambio', ['huella', 'traza', 'tenant', 'unidad', 'sku', 'publicacion',
    'variante', 'cantidad', 'costo', 'version_costo', 'fecha_costo', 'incluye', 'prevision', 'extra',
    'venta_anterior', 'otra_cuenta', 'origen_real', 'enlace_nulo', 'linea_duplicada'])
def test_archivo_incoherente_no_reemplaza_fuentes_ni_prevision(cambio):
    d = documento()
    x = d['lineas'][0]
    if cambio == 'huella':d['enlace_precio']['neto_minimo_centavos'] += 1
    if cambio == 'traza':d['enlace_precio']['traza']['sku'] = 'otro'
    if cambio == 'tenant':d['organizacion_id'] = 8
    if cambio == 'unidad':d['unidad_negocio_id'] = 8
    if cambio == 'sku':x['sku'] = 'otro'
    if cambio == 'publicacion':x['publicacion_id'] = 'otra'
    if cambio == 'variante':x['variante_id'] = 'otra'
    if cambio == 'cantidad':x['cantidad'] = 2
    if cambio == 'costo':x['costo_snapshot']['unitario_centavos'] += 1
    if cambio == 'version_costo':x['costo_snapshot']['version'] = 'otra'
    if cambio == 'fecha_costo':x['costo_snapshot']['vigente_desde'] = '2026-10-01T00:00:00Z'
    if cambio == 'incluye':x['costo_snapshot']['incluye_embalaje'] = True
    if cambio == 'prevision':x['previsto']['liquidacion_centavos'] += 1
    if cambio == 'extra':d['gastos_locales_previstos_centavos'] = 0
    if cambio == 'venta_anterior':x['fecha_venta'] = (AHORA-timedelta(seconds=1)).isoformat()+'Z'
    if cambio == 'otra_cuenta':d['cuenta_codigo'] = 'CUENTA-UAT'
    if cambio == 'origen_real':d['origen'] = 'archivo_offline'
    if cambio == 'enlace_nulo':d['enlace_precio'] = None
    if cambio == 'linea_duplicada':otro=deepcopy(x);otro['linea_id']='otra';otro['order_id']='otra';d['lineas'].append(otro)
    with pytest.raises(ValueError):analizar(d)


def test_rehacer_huellas_no_alcanza_si_la_prevision_no_reproduce_el_motor():
    d = documento()
    e = d['enlace_precio']
    t = e['traza']
    t['minimo']['precio_final_centavos'] += 100
    t['huella_enlace'] = _huella({k:v for k,v in t.items() if k!='huella_enlace'})
    e['huella_snapshot'] = _huella({k:v for k,v in e.items() if k!='huella_snapshot'})
    # Se actualizan referencias, pero el precio deja de ser el primero admisible.
    d['lineas'][0]['costo_snapshot']['fuente'] = f"Snapshot de ensayo {e['huella_snapshot']}"
    d['lineas'][0]['previsto']['fuente'] = f"Cálculo congelado {e['huella_snapshot']}"
    with pytest.raises(ValueError, match='mínimo económico'):analizar(d)


@pytest.mark.parametrize('cambio', ['tasa_ausente', 'tramos_ausentes', 'tramos_excesivos', 'embalaje_contradictorio'])
def test_fotografia_recalculada_no_admite_faltantes_como_cero(cambio):
    d = documento()
    e = d['enlace_precio'];t = e['traza']
    if cambio == 'tasa_ausente':t['politica_canal']['publicidad_pct'] = None
    if cambio == 'tramos_ausentes':t['tramos'] = []
    if cambio == 'tramos_excesivos':t['tramos'] *= 201
    if cambio == 'embalaje_contradictorio':t['evidencia_embalaje']['modo_embalaje'] = 'sin_costo'
    t['huella_enlace'] = _huella({k:v for k,v in t.items() if k!='huella_enlace'})
    e['huella_snapshot'] = _huella({k:v for k,v in e.items() if k!='huella_snapshot'})
    d['lineas'][0]['costo_snapshot']['fuente'] = f"Snapshot de ensayo {e['huella_snapshot']}"
    d['lineas'][0]['previsto']['fuente'] = f"Cálculo congelado {e['huella_snapshot']}"
    with pytest.raises(ValueError):analizar(d)


@pytest.mark.parametrize('estado', ['pendiente', 'requiere_revision'])
def test_no_prepara_venta_con_embalaje_no_vigente(estado):
    f = fila(producto_uat())
    f['trazabilidad_economica']['cobertura_estado'] = estado
    with pytest.raises(ValueError, match='embalaje'):preparar_venta_prueba(f, ahora=AHORA)


def test_caso_desconocido_y_envio_imposible_se_rechazan():
    f = fila(producto_uat())
    with pytest.raises(ValueError):preparar_venta_prueba(f, caso='real', ahora=AHORA)
    # El escenario genérico de bajo importe no admite ese aumento fijo.
    datos=fuentes();guardar(fila(datos));f=fila(datos)
    with pytest.raises(ValueError, match='supera'):preparar_venta_prueba(f, caso='envio_mayor', ahora=AHORA)


@pytest.mark.parametrize('cambio', ['base', 'envio_mayor', 'unidad', 'inclusion', 'lista', 'huella',
    'duplicado', 'embalaje_pendiente', 'caso_invalido', 'sin_acceso'])
def test_ruta_real_renderiza_el_ensayo_o_rechaza_contexto_sin_escrituras(cambio):
    import ast
    from pathlib import Path
    import re
    from flask import Flask, request, redirect, render_template, url_for
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    from services.escenarios_rentabilidad_ml import ESCENARIOS
    from services.venta_prueba_precio import CASOS
    from services.presentacion_monetaria import formatear_centavos_ars
    codigo = ast.parse(Path('modules/admin/comercial/routes.py').read_text())
    funcion = next(n for n in ast.walk(codigo) if isinstance(n, ast.FunctionDef) and n.name == 'venta_prueba_precio')
    assert any('login_required' in ast.unparse(n) for n in funcion.decorator_list)
    funcion.decorator_list = []
    datos = producto_uat()
    f = fila(datos)
    filas = [f, f] if cambio == 'duplicado' else [f]
    if cambio == 'embalaje_pendiente':f['trazabilidad_economica']['cobertura_estado']='pendiente'
    llamadas = []
    def consultar(org, unidad, **kw):
        llamadas.append((org, unidad))
        return {'simulaciones_canal':filas}
    contexto = dict(request=request, redirect=redirect, render_template=render_template, url_for=url_for,
        acceso=lambda:(Obj(id=9),Obj(id=1),redirect('/sin-acceso') if cambio=='sin_acceso' else None),
        contexto_comercial=lambda *a:(Obj(id=2, nombre='Unidad de ensayo'),[]), modelos={},
        obtener_datos_panel_comercial=consultar,
        preparar_venta_prueba=lambda *a,**kw:preparar_venta_prueba(*a,ahora=AHORA,**kw),
        analizar_rentabilidad=analizar_rentabilidad, CUENTA_ENSAYO=CUENTA,
        CASOS_VENTA_PRECIO=CASOS, ESCENARIOS_RENTABILIDAD=ESCENARIOS)
    exec(compile(ast.Module(body=[funcion],type_ignores=[]),'ruta','exec'),contexto)
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.jinja_loader = ChoiceLoader([DictLoader({'base.html':'<!doctype html>{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')])
    app.jinja_env.filters['moneda_centavos'] = formatear_centavos_ars
    for endpoint in ('admin_comercial.panel','admin_comercial.simulador_integral_comercial','admin_rentabilidad_ml.panel','admin_rentabilidad_ml.archivo'):
        app.add_url_rule('/'+endpoint, endpoint=endpoint,view_func=lambda:'test')
    app.add_url_rule('/ensayo', endpoint='admin_comercial.venta_prueba_precio',view_func=contexto['venta_prueba_precio'])
    params = dict(unidad_negocio_id=2,catalogo_producto_id=5,lista_precio_id=6,
        huella_calculo=f['trazabilidad_economica']['huella_enlace'])
    if cambio=='unidad':params['unidad_negocio_id']=3
    if cambio=='inclusion':params['catalogo_producto_id']=99
    if cambio=='lista':params['lista_precio_id']=99
    if cambio=='huella':params['huella_calculo']='vieja'
    if cambio=='envio_mayor':params['caso_enlace']='envio_mayor'
    if cambio=='caso_invalido':params['caso_enlace']='cobro_real'
    r = app.test_client().get('/ensayo',query_string=params)
    if cambio in {'base','envio_mayor'}:
        assert r.status_code==200 and r.headers['Cache-Control']=='no-store'
        assert 'Una unidad' in r.text and 'Fuentes del cálculo congelado' in r.text
        assert 'Comparar venta de prueba' in r.text and 'Descargar ensayo con cálculo congelado' in r.text
        assert '#politicas' in r.text
        assert ('por debajo del mínimo' in r.text) == (cambio=='envio_mayor')
        source = re.search(r'id="evidencia-archivo"[^>]*>(.*?)</script>',r.text,re.S)
        paquete = json.loads(source.group(1))
        _, nuevo = analizar_archivo(json.dumps(paquete).encode(),organizacion_id=1,unidad_negocio_id=2,cuenta_codigo=CUENTA)
        assert nuevo == paquete['resultado']
    else:
        assert r.status_code==302
    assert llamadas == ([] if cambio in {'unidad','sin_acceso'} else [(1,2)])


def test_popup_presenta_acceso_solo_con_evidencia_guardada_y_no_anida_formularios():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('templates'),autoescape=True)
    env.globals['url_for'] = lambda endpoint,**kw: '/'+endpoint
    f = fila(producto_uat())
    template = env.get_template('partials/enlace_economico_dialog.html')
    html = template.render(fila=f)
    assert 'Preparar venta de prueba' in html and 'Los cambios sin guardar' in html
    assert html.count('<form ')==1 and html.count('</form>')==1
    f['trazabilidad_economica']['cobertura_estado']='requiere_revision'
    assert 'Preparar venta de prueba' not in template.render(fila=f)
