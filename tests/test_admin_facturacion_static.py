from pathlib import Path


def leer(nombre):
    return Path(nombre).read_text(
        encoding="utf-8"
    )


def test_facturacion_usa_blueprint_propio():
    rutas = leer(
        "modules/admin/facturacion/routes.py"
    )

    assert "Blueprint(" in rutas
    assert (
        '@blueprint.route("/admin/facturacion")'
        in rutas
    )
    assert (
        '"/admin/facturacion/guardar"'
        in rutas
    )


def test_app_solo_registra_modulo_fiscal():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )
    bootstrap = Path(
        "services/bootstrap_modulos_web.py"
    ).read_text(encoding="utf-8")

    assert "registrar_modulos_web(" in app
    assert (
        "crear_blueprint_facturacion"
        in bootstrap
    )
    assert "app.register_blueprint(" in bootstrap
    assert (
        "def admin_facturacion("
        not in app
    )
    assert (
        "def admin_facturacion_guardar("
        not in app
    )
    assert (
        '@app.route("/admin/facturacion")'
        not in app
    )
    assert (
        "procesar_accion_facturacion_admin"
        not in app
    )


def test_blueprint_resuelve_tenant_autorizado():
    rutas = leer(
        "modules/admin/facturacion/routes.py"
    )

    assert "resolver_tenant_usuario(" in rutas
    assert "session.get(" in rutas
    assert '"organizacion_id"' in rutas
    assert 'membresia.rol != "admin"' in rutas
    assert (
        'session["organizacion_id"]'
        in rutas
    )
    assert 'slug="grupo-fierro"' not in rutas

def test_blueprint_delega_consultas_y_operaciones():
    rutas = leer(
        "modules/admin/facturacion/routes.py"
    )

    assert (
        "obtener_datos_panel_facturacion("
        in rutas
    )
    assert (
        "procesar_accion_facturacion_admin("
        in rutas
    )
    assert ".query" not in rutas


def test_blueprint_conserva_rollback_y_auditoria():
    rutas = leer(
        "modules/admin/facturacion/routes.py"
    )

    assert "db.session.rollback()" in rutas
    assert "registrar_auditoria(" in rutas
    assert (
        '"Configuró facturación multi-CUIT"'
        in rutas
    )


def test_template_usa_endpoints_namespaced():
    template = leer(
        "templates/admin_facturacion.html"
    )
    base = leer("templates/base.html")

    assert (
        "url_for('admin_facturacion.guardar')"
        in template
    )
    assert (
        "url_for('admin_facturacion_guardar')"
        not in template
    )
    assert (
        "url_for('admin_facturacion.panel')"
        in base
    )


def test_panel_declara_bloqueo_productivo():
    template = leer(
        "templates/admin_facturacion.html"
    ).lower()

    assert "conexión con arca" in template
    assert "emisión real" in template
    assert "bloqueada" in template


def test_modulo_fiscal_no_consume_pedidos():
    archivos = (
        "modules/admin/facturacion/routes.py",
        "services/facturacion_consultas.py",
        "services/facturacion_admin.py",
        "services/facturacion_nucleo.py",
    )

    for nombre in archivos:
        fuente = leer(nombre)

        assert "Pedido.query" not in fuente
        assert "ml_api_" not in fuente
        assert "TiendaNubeCuenta" not in fuente
        assert "requests." not in fuente
