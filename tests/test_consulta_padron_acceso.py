"""Ejecuta los blueprints reales sin importar el monolito ni servicios operativos."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, Blueprint, redirect, session, url_for
from services import consulta_padron_web


@pytest.mark.parametrize('modulo', ['compras','crm'])
@pytest.mark.parametrize('rol', ['admin','carga','sin_acceso'])
def test_solo_admin_del_tenant_puede_consultar(modulo, rol, monkeypatch):
    archivo = f'modules/admin/{modulo}/routes.py'
    arbol = ast.parse(Path(archivo).read_text())
    arbol.body = [n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == f'crear_blueprint_{modulo}']
    org = SimpleNamespace(id=71)
    class TenantError(ValueError): pass
    def resolver(*args, **kwargs):
        if rol == 'sin_acceso': raise TenantError('Sin organización')
        return SimpleNamespace(rol=rol, organizacion_id=71, organizacion=org)
    ns = dict(__name__=__name__, Blueprint=Blueprint, session=session, redirect=redirect, url_for=url_for,
        resolver_tenant_usuario=resolver, TenantError=TenantError)
    exec(compile(arbol, archivo, 'exec'), ns)
    app = Flask(__name__); app.secret_key = 'prueba'
    app.add_url_rule('/', endpoint='inicio', view_func=lambda: 'Inicio')
    query = Mock(); query.filter_by.return_value.order_by.return_value.all.return_value = [SimpleNamespace(id=4)]
    unidad = SimpleNamespace(query=query, nombre=SimpleNamespace(asc=lambda:None))
    dependencias = {'db':None, 'modelos':{'UnidadNegocio':unidad}, 'UsuarioOrganizacion':None,
        'usuario_actual':lambda:SimpleNamespace(id=3), 'login_required':lambda f:f, 'registrar_auditoria':lambda *a,**kw:None}
    app.register_blueprint(ns[f'crear_blueprint_{modulo}'](dependencias=dependencias))
    consultar = Mock(return_value={'cuit':'20224107030'})
    monkeypatch.setattr(consulta_padron_web, 'consultar_cuit', consultar)
    cliente = app.test_client()
    respuesta = cliente.post(f'/admin/{modulo}/consultar-cuit', data={'cuit':'20224107030','organizacion_id':'999'})
    if rol == 'admin':
        assert respuesta.status_code == 200
        consultar.assert_called_once_with(71, '20224107030')
    else:
        assert respuesta.status_code == 302
        consultar.assert_not_called()
    assert cliente.get(f'/admin/{modulo}/consultar-cuit').status_code == 405
