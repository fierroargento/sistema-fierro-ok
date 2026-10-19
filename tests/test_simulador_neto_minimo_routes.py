"""Ejecuta la función de ruta real sin arrancar canales, scheduler ni DB."""
import ast
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, render_template, request
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
import pytest

from services.presentacion_monetaria import formatear_centavos_ars
from services.simulador_integral_comercial import ESCENARIOS, escenario_predefinido, simular_escenario


def extraer(path,nombre,entorno):
    nodo=next(n for n in ast.walk(ast.parse(Path(path).read_text()))
              if isinstance(n,ast.FunctionDef) and n.name==nombre)
    nodo.decorator_list=[]
    exec(compile(ast.Module(body=[nodo],type_ignores=[]),path,'exec'),entorno)
    return entorno[nombre]


@pytest.fixture
def cliente():
    app=Flask(__name__);app.config['TESTING']=True
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')])
    app.add_url_rule('/admin/comercial',endpoint='admin_comercial.panel',view_func=lambda:'Comercial')
    importe=extraer('services/catalogos_comerciales.py','importe_a_centavos',
                    dict(Decimal=Decimal,InvalidOperation=InvalidOperation,ROUND_HALF_UP=ROUND_HALF_UP))
    entorno=dict(request=request,render_template=render_template,ESCENARIOS=ESCENARIOS,
        escenario_predefinido=escenario_predefinido,simular_escenario=simular_escenario,
        importe_a_centavos=importe,formatear_centavos_ars=formatear_centavos_ars,acceso=lambda:(None,SimpleNamespace(id=1),None),
        contexto_comercial=lambda org:(SimpleNamespace(id=3,nombre='Unidad de ensayo'),[]))
    ruta=extraer('modules/admin/comercial/routes.py','simulador_integral_comercial',entorno)
    app.add_url_rule('/simulador',view_func=ruta,methods=['GET','POST'])
    return app.test_client()


def datos(**cambios):
    d=dict(modo='personalizado',escenario='cargo_fijo',costo='4.000,00',
        minimo_neto='5.000,00',utilidad_pct='99',impuesto_pct='99',
        precio_final='6.000,00',comision_pct='15',publicidad_pct='3',
        financiacion_pct='2',devoluciones_pct='1',cargo_fijo='100',
        umbral_envio='10000',envio='1000',liquidacion_real='4500',
        estado_venta='confirmada',paso_precio='0,01',descuento_pct='0')
    d.update(cambios);return d


def test_post_respeta_minimo_neto_coma_decimal_y_desglosa_cargos(cliente):
    r=cliente.post('/simulador',data=datos())
    assert r.status_code==200 and 'Simulación actualizada' in r.text
    assert 'Monto declarado para el ensayo' in r.text
    assert 'Desglose del precio mínimo calculado' in r.text
    assert 'Neto al precio mínimo calculado' in r.text
    assert '5000.00' in r.text and '6.455,69' in r.text
    assert 'Publicidad' in r.text and 'Financiación' in r.text
    assert 'no consulta canales externos' in r.text


def test_sin_minimo_explicito_conserva_la_regla_ilustrativa(cliente):
    r=cliente.post('/simulador',data=datos(minimo_neto='',utilidad_pct='20',impuesto_pct='5'))
    assert r.status_code==200 and 'Regla ilustrativa de costo, utilidad e impuestos' in r.text
    assert 'Simulación actualizada' in r.text


@pytest.mark.parametrize('cambios',[{'minimo_neto':'100'},{'paso_precio':'0'},{'comision_pct':'99'}])
def test_rechazo_no_muestra_un_precio_valido(cliente,cambios):
    r=cliente.post('/simulador',data=datos(**cambios))
    assert 'comercial-message-error' in r.text
    assert 'Desglose del precio mínimo calculado' not in r.text
