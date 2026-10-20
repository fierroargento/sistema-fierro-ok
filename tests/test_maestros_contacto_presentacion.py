"""Render real de ambas altas y su enlace al CUIT, sin invocar el monolito."""
import re

def test_altas_reales_conservan_campos_y_vinculan_consulta_al_formulario_correcto():
    from pathlib import Path
    from types import SimpleNamespace as NS
    from flask import Flask, render_template
    from jinja2 import ChoiceLoader, FileSystemLoader, DictLoader, StrictUndefined
    app=Flask(__name__)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block extra_head %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')])
    app.jinja_env.undefined=StrictUndefined
    app.jinja_env.globals['url_for']=lambda endpoint,**kw:'/'+endpoint
    org=NS(nombre='Ensayo UAT')
    proveedor=NS(id=1,codigo='PRUEBA',razon_social='Proveedor <prueba>',cuit='20224107030',estado='activo',telefono='GENERAL',persona_contacto='Persona',email='mail@prueba.com',domicilio='Calle 123',localidad='Viedma',provincia='Río Negro',codigo_postal='8500',observacion='')
    cliente=NS(id=1,codigo='C-PRUEBA',nombre='Cliente <prueba>',documento='20224107030',telefono='1234',email='mail@prueba.com',unidad_negocio=None,localidad='Viedma',provincia='Río Negro',estado='potencial',activo=False)
    with app.test_request_context('/admin/compras?vista=proveedores'):
     html=render_template('admin_compras.html',csp_nonce='prueba',csrf_token_value='csrf-prueba',organizacion=org,ok_feedback='',error='',proveedores=[proveedor],contactos_preparados=True,contactos_proveedores={1:'CONTACTO'},unidad_activa=NS(nombre='UAT'))
     assert 'data-arca-form="proveedor"' in html
     assert 'CONTACTO' in html
    with app.test_request_context('/admin/crm?vista=clientes'):
     html=render_template('admin_crm.html',csp_nonce='prueba',csrf_token_value='csrf-prueba',organizacion=org,ok_feedback='',error='',clientes=[cliente],unidades=[],domicilios_preparados=True,domicilios_clientes={1:{'domicilio':'Calle 123','codigo_postal':'8500'}},identidades=[],oportunidades=[],etapas=[],actividades=[])
     assert 'data-arca-form="cliente"' in html
     assert 'Calle 123' in html
    for tipo, accion in [('proveedor','crear_proveedor'), ('cliente','crear_cliente')]:
        # El bloque de cliente renderizado corresponde al alta, nunca a etapas u oportunidades.
        with app.test_request_context('/admin/crm?vista=clientes' if tipo == 'cliente' else '/admin/compras?vista=proveedores'):
            contexto = dict(csp_nonce='prueba', csrf_token_value='csrf-prueba', organizacion=org,
                ok_feedback='', error='', proveedores=[proveedor], contactos_preparados=True,
                contactos_proveedores={1:'CONTACTO'}, unidad_activa=NS(nombre='UAT'), clientes=[cliente],
                unidades=[], domicilios_preparados=True, domicilios_clientes={}, identidades=[],
                oportunidades=[], etapas=[], actividades=[])
            html = render_template('admin_crm.html' if tipo == 'cliente' else 'admin_compras.html', **contexto)
        formulario = re.search(r'<form[^>]*data-arca-form="' + tipo + r'"[^>]*>(.*?)</form>', html, re.S).group(1)
        assert 'value="' + accion + '"' in formulario
        assert 'data-arca-consult' in formulario and 'data-arca-apply' in formulario
        assert 'name="domicilio"' in formulario and 'name="codigo_postal"' in formulario
        assert 'Nombre &lt;' not in formulario  # El alta comienza vacía.
        assert 'Cliente <prueba>' not in html and 'Proveedor <prueba>' not in html
