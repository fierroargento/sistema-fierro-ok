"""Verifica los datos y acciones que ve el usuario, usando la plantilla real."""
from datetime import datetime
from types import SimpleNamespace

import pytest
from flask import Flask, render_template
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader, StrictUndefined

from services.importacion_fuentes_costeo import definicion, presentar_vista_fuentes


def renderizar(tipo, vista, confirmado=False):
    app = Flask(__name__)
    app.jinja_loader = ChoiceLoader([
        DictLoader({'base.html': '{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),
        FileSystemLoader('templates'),
    ])
    app.jinja_env.undefined = StrictUndefined
    app.jinja_env.globals['url_for'] = lambda endpoint, **kw: '/' + endpoint
    columnas, filas = presentar_vista_fuentes(tipo, vista)
    lote = SimpleNamespace(id=1, estado='confirmado' if confirmado else 'mapeado',
        modo='crear_actualizar', nombre_archivo='lista <prueba>.xlsx', total_filas=len(vista),
        creados=33, actualizados=0, rechazados=0, fecha_creacion=datetime(2026, 10, 20, 19, 27))
    with app.test_request_context('/'):
        return render_template('admin_importacion_fuentes_costeo.html',
            csp_nonce='prueba', config=definicion(tipo), tipo=tipo,
            unidad_activa=SimpleNamespace(nombre='Ensayo UAT'), error=None,
            mostrar_configuracion=False, lote=lote, vista=vista, columnas_vista=columnas,
            vista_presentada=filas, resumen_vista={'crear': 1, 'actualizar': 0, 'rechazado': 1, 'aplicables': 1},
            historial=[lote])


def test_insumos_agrupados_conservan_cada_campo_y_el_motivo_del_rechazo():
    vista = [{'numero': 2, 'accion': 'crear', 'datos': {
        'codigo': 'PERFIL-6M', 'nombre': 'Perfil <especial>', 'tipo': 'materia_prima',
        'unidad_medida': 'metro', 'precio_unitario': '100', 'proveedor': 'Proveedor & Cía',
        'cantidad_bulto': '6', 'medidas_origen': 'Barra de 6 metros', 'base_precio': 'bulto',
        'precio_bulto': '600'}, 'errores': []},
        {'numero': 3, 'accion': 'rechazado', 'datos': {'codigo': 'INVALIDO'},
         'errores': ['Falta la cantidad por bulto <obligatoria>']}]
    html = renderizar('insumos', vista)
    assert 'Perfil &lt;especial&gt;' in html and 'Perfil <especial>' not in html
    assert 'Proveedor &amp; Cía' in html
    for dato in ('PERFIL-6M', 'Materia prima', 'metro', '$ 100,00', 'Barra de 6 metros', 'Por bulto', '$ 600,00'):
        assert dato in html
    assert 'Cantidad por bulto: 6' in html
    assert 'Falta la cantidad por bulto &lt;obligatoria&gt;' in html
    assert 'name="accion" value="confirmar"' in html
    assert '¿Confirmás la importación?' in html


@pytest.mark.parametrize('tipo', ['empleados', 'recursos', 'maquinas', 'costos-fijos', 'fichas'])
def test_otras_fuentes_conservan_todas_las_columnas(tipo):
    html = renderizar(tipo, [{'numero': 2, 'accion': 'rechazado', 'datos': {}, 'errores': ['Revisar fila']}])
    for columna in definicion(tipo)['campos'].values():
        assert columna[0] in html
    assert 'Revisar fila' in html


def test_lote_confirmado_muestra_resultado_sin_permitir_reaplicarlo():
    html = renderizar('insumos', [{'numero': 2, 'datos': {}, 'errores': ['Ya confirmado']}], confirmado=True)
    assert 'Importación finalizada' in html and '<strong>33</strong> creados' in html
    assert 'lista &lt;prueba&gt;.xlsx' in html
    assert 'name="accion" value="confirmar"' not in html
    assert 'id="vista-previa"' not in html
    assert 'Cómo cargar precios' not in html
