import importlib.util
import io
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace as O
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask
from services.contabilidad_errores import mensaje_error_contable


class ErrorBaseDatos(Exception):
    def __init__(self, restriccion=None):
        super().__init__("SQL INSERT INTO asiento_contable_borrador parametros privados")
        self.orig = O(diag=O(constraint_name=restriccion))


@pytest.mark.parametrize("restriccion,mensaje", [
    ("uq_asiento_borrador_clave", "Este asiento borrador ya existe. No se creó un duplicado."),
    ("uq_cuenta_contable_tenant_unidad", "Ya existe una cuenta con ese código en la unidad activa."),
    ("otra_restriccion", "No se pudo completar la operación contable. Intentá nuevamente."),
])
def test_errores_de_base_no_exponen_sql(restriccion, mensaje):
    assert mensaje_error_contable(ErrorBaseDatos(restriccion)) == mensaje


def test_validacion_conserva_el_aviso_y_error_desconocido_no_filtra_detalles():
    assert mensaje_error_contable(ValueError("El importe debe ser mayor que cero.")) == "El importe debe ser mayor que cero."
    assert "INSERT" not in mensaje_error_contable(RuntimeError("INSERT INTO tabla privada"))


@pytest.mark.parametrize("importacion", [False, True])
def test_ruta_rechaza_duplicado_con_rollback_y_aviso_publico(monkeypatch, importacion):
    tenant = ModuleType("services.tenant_context")
    tenant.TenantError = type("TenantError", (Exception,), {})
    tenant.resolver_tenant_usuario = lambda *args, **kwargs: O(rol="admin", organizacion_id=1, organizacion=O(id=1))
    monkeypatch.setitem(sys.modules, "services.tenant_context", tenant)
    spec = importlib.util.spec_from_file_location("contabilidad_ruta_prueba", Path("modules/admin/contabilidad/routes.py"))
    rutas = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rutas)
    def falla(*args, **kwargs):
        raise ErrorBaseDatos("uq_asiento_borrador_clave")
    monkeypatch.setattr(rutas, "crear_borrador", falla)
    monkeypatch.setattr(rutas, "importar_borradores", falla)
    class Query:
        def filter_by(self, **kwargs):return self
        def first(self):return O(id=3)
        def all(self):return []
    modelo = O(query=Query())
    class Session:
        rollbacks = 0
        def rollback(self):self.rollbacks += 1
    db_session = Session()
    auditorias = []
    app = Flask(__name__)
    app.secret_key = "prueba-local"
    app.register_blueprint(rutas.crear_blueprint_contabilidad(dependencias={
        "db": O(session=db_session), "modelos": {nombre:modelo for nombre in ["UnidadNegocio", "CuentaContable", "AsientoContableBorrador", "LineaAsientoContableBorrador"]},
        "usuario_actual": lambda:O(id=1), "UsuarioOrganizacion":object, "login_required":lambda f:f,
        "registrar_auditoria":lambda *args, **kwargs:auditorias.append(args),
    }))
    client = app.test_client()
    if importacion:
        response = client.post("/admin/contabilidad/importar-borradores", data={"borradores":(io.BytesIO(b"{}"), "uat.json")})
    else:
        response = client.post("/admin/contabilidad/guardar", data={"accion":"crear_borrador", "cuenta_debe_id":"1", "cuenta_haber_id":"2"})
    assert response.status_code == 302 and db_session.rollbacks == 1 and auditorias == []
    assert parse_qs(urlparse(response.location).query)["error"] == ["Este asiento borrador ya existe. No se creó un duplicado."]
    assert "INSERT" not in response.location and "parametros" not in response.location


@pytest.mark.parametrize("desde,hasta,mensaje", [
    ("2026-10-08", "2026-10-07", "El inicio del periodo no puede ser posterior al cierre."),
    ("fecha-invalida", "2026-10-07", "El periodo contable no es valido."),
    ("2026-10-07", "2026-02-30", "El periodo contable no es valido."),
    ("2026-10-07", "2026-10-07", None),
])
def test_reporte_valida_periodo_sin_error_500_ni_escrituras(monkeypatch, desde, hasta, mensaje):
    tenant = ModuleType("services.tenant_context")
    tenant.TenantError = type("TenantError", (Exception,), {})
    tenant.resolver_tenant_usuario = lambda *args, **kwargs: O(rol="admin", organizacion_id=1, organizacion=O(id=1))
    monkeypatch.setitem(sys.modules, "services.tenant_context", tenant)
    spec = importlib.util.spec_from_file_location("contabilidad_reporte_prueba", Path("modules/admin/contabilidad/routes.py"))
    rutas = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rutas)
    class Query:
        def filter_by(self, **kwargs):return self
        def first(self):return O(id=3)
        def all(self):return []
    modelo = O(query=Query())
    class Session:
        def __getattr__(self, nombre):
            raise AssertionError("El reporte no debe escribir ni alterar la sesión: " + nombre)
    app = Flask(__name__)
    app.secret_key = "prueba-local"
    def auditar(*args, **kwargs):
        raise AssertionError("La consulta no debe registrar una operación contable.")
    app.register_blueprint(rutas.crear_blueprint_contabilidad(dependencias={
        "db": O(session=Session()), "modelos": {nombre:modelo for nombre in ["UnidadNegocio", "CuentaContable", "AsientoContableBorrador", "LineaAsientoContableBorrador"]},
        "usuario_actual": lambda:O(id=1), "UsuarioOrganizacion":object, "login_required":lambda f:f,
        "registrar_auditoria":auditar,
    }))
    response = app.test_client().get("/admin/contabilidad/reportes-borrador",
        query_string={"desde":desde, "hasta":hasta})
    if mensaje:
        assert response.status_code == 302
        assert urlparse(response.location).path == "/admin/contabilidad"
        assert parse_qs(urlparse(response.location).query)["error"] == [mensaje]
    else:
        assert response.status_code == 200
        assert response.json["aprobado"] is True
        assert response.json["periodo"] == {"desde":desde, "hasta":hasta}
        assert "attachment" in response.headers["Content-Disposition"]
