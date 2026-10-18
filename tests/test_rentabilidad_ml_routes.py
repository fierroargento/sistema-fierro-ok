from functools import wraps
from pathlib import Path
from types import SimpleNamespace as Obj

from flask import Flask, redirect, session
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
import pytest

from modules.admin.rentabilidad_ml.routes import crear_blueprint_rentabilidad_ml
from services.escenarios_rentabilidad_ml import ESCENARIOS
from services.presentacion_monetaria import formatear_centavos_ars


class Query:
    def __init__(self, rows): self.rows = rows
    def filter_by(self, **kw):
        return Query([r for r in self.rows if all(getattr(r, k, None) == v for k, v in kw.items())])
    def all(self): return list(self.rows)
    def first(self): return self.rows[0] if self.rows else None


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = "test-only"
    app.config["TESTING"] = True
    app.jinja_loader = ChoiceLoader([DictLoader({"base.html": "<!doctype html><html><head>{% block extra_head %}{% endblock %}</head><body>{% block content %}{% endblock %}</body></html>"}), FileSystemLoader("templates")])
    app.jinja_env.filters["moneda_centavos"] = formatear_centavos_ars
    app.add_url_rule("/admin/comercial", endpoint="admin_comercial.panel", view_func=lambda: "Comercial")
    app.add_url_rule("/admin/comercial/simulador-integral", endpoint="admin_comercial.simulador_integral_comercial", view_func=lambda: "Simulador")
    def login_required(fn):
        @wraps(fn)
        def wrapped(*a, **kw):
            if not session.get("logged_in"): return redirect("/login")
            return fn(*a, **kw)
        return wrapped
    miembros = [Obj(usuario_id=1, organizacion_id=1, rol="admin", activa=True, predeterminada=True),
                Obj(usuario_id=2, organizacion_id=1, rol="carga", activa=True, predeterminada=True)]
    unidades = [Obj(id=3, organizacion_id=1, activa=True, nombre="Ensayo <UAT>"),
                Obj(id=4, organizacion_id=2, activa=True, nombre="Ajena")]
    app.register_blueprint(crear_blueprint_rentabilidad_ml(dependencias={
        "login_required": login_required, "usuario_actual": lambda: Obj(id=session.get("uid", 1)),
        "UsuarioOrganizacion": Obj(query=Query(miembros)), "UnidadNegocio": Obj(query=Query(unidades))}))
    return app


def ingresar(client, **kw):
    with client.session_transaction() as s:
        s.update(logged_in=True, uid=1, organizacion_id=1, unidad_negocio_id=3)
        s.update(kw)


@pytest.mark.parametrize("caso", ESCENARIOS)
def test_render_y_exportacion_con_contexto_autorizado(app, caso):
    client = app.test_client(); ingresar(client)
    r = client.get("/admin/comercial/rentabilidad-ml", query_string={"caso": caso, "analizar": "1"})
    assert r.status_code == 200
    assert "Análisis terminado" in r.text and "Ensayo &lt;UAT&gt;" in r.text
    assert "Ver detalle" in r.text and "Guardar" not in r.text
    e = client.get("/admin/comercial/rentabilidad-ml", query_string={"caso": caso, "descargar": "1"})
    assert e.status_code == 200
    assert e.json["resultado"]["organizacion_id"] == 1 and e.json["resultado"]["unidad_negocio_id"] == 3
    assert e.json["resultado"]["origen"] == "sintetico"
    assert e.json["entrada"]["cuenta_codigo"] == "demo-rentabilidad-sin-conexion"


def test_sesion_unidad_ajena_no_es_fallback_a_primera_unidad(app):
    c = app.test_client(); ingresar(c, unidad_negocio_id=4)
    r = c.get("/admin/comercial/rentabilidad-ml?analizar=1")
    assert r.status_code == 302 and "/admin/comercial?" in r.location


def test_organizacion_ajena_y_rol_no_admin_no_acceden(app):
    c = app.test_client(); ingresar(c, organizacion_id=2)
    assert c.get("/admin/comercial/rentabilidad-ml?descargar=1").status_code == 403
    ingresar(c, uid=2)
    assert c.get("/admin/comercial/rentabilidad-ml").status_code == 403


def test_login_y_metodos_de_escritura_bloqueados(app):
    c = app.test_client()
    assert c.get("/admin/comercial/rentabilidad-ml").location == "/login"
    ingresar(c)
    assert c.post("/admin/comercial/rentabilidad-ml").status_code == 405


def test_caso_desconocido_muestra_error_escapado_y_no_descarga(app):
    c = app.test_client(); ingresar(c)
    r = c.get("/admin/comercial/rentabilidad-ml?analizar=1&caso=%3Cscript%3E")
    assert r.status_code == 400 and "Elegí uno" in r.text and "<script>" not in r.text


def test_inicio_no_simula_y_contexto_query_no_reemplaza_sesion(app):
    c = app.test_client(); ingresar(c)
    assert "Análisis terminado" not in c.get("/admin/comercial/rentabilidad-ml").text
    r = c.get("/admin/comercial/rentabilidad-ml?descargar=1&organizacion_id=2&unidad_negocio_id=4&cuenta_codigo=otra")
    assert r.json["resultado"]["organizacion_id"] == 1
    assert r.json["resultado"]["unidad_negocio_id"] == 3
