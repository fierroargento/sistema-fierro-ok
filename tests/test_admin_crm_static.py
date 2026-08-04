from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def _leer(ruta):
    return (
        RAIZ
        .joinpath(ruta)
        .read_text(encoding="utf-8")
    )


def test_crm_usa_blueprint_modular():
    rutas = _leer(
        "modules/admin/crm/routes.py"
    )

    assert "Blueprint(" in rutas
    assert '"admin_crm"' in rutas
    assert '"/admin/crm"' in rutas
    assert (
        '"/admin/crm/guardar"'
        in rutas
    )


def test_panel_resuelve_tenant_admin():
    rutas = _leer(
        "modules/admin/crm/routes.py"
    )

    assert (
        "resolver_tenant_usuario("
        in rutas
    )
    assert (
        'session.get(\n'
        '                    "organizacion_id"'
        in rutas
    )
    assert (
        'membresia.rol != "admin"'
        in rutas
    )
    assert (
        'session["organizacion_id"]'
        in rutas
    )


def test_panel_delega_consultas_tenant():
    rutas = _leer(
        "modules/admin/crm/routes.py"
    )

    assert (
        "obtener_datos_panel_crm("
        in rutas
    )
    assert ".query" not in rutas
    assert '"admin_crm.html"' in rutas


def test_guardado_delega_y_hace_rollback():
    rutas = _leer(
        "modules/admin/crm/routes.py"
    )

    assert (
        "procesar_accion_crm_admin("
        in rutas
    )
    assert "db.session.rollback()" in rutas
    assert "registrar_auditoria(" in rutas
    assert '"admin_crm.panel"' in rutas


def test_app_solo_compone_blueprint_crm():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )
    bootstrap = Path(
        "services/bootstrap_modulos_web.py"
    ).read_text(encoding="utf-8")

    assert "registrar_modulos_web(" in app
    assert "crear_blueprint_crm(" in bootstrap
    assert "app.register_blueprint(" in bootstrap
    assert "def admin_crm()" not in app
    assert (
        "def admin_crm_guardar()"
        not in app
    )


def test_servicios_crm_no_tocan_produccion():
    servicios = (
        _leer("services/crm_admin.py")
        + _leer("services/crm_consultas.py")
        + _leer("services/crm_nucleo.py")
    )

    prohibidos = [
        "Pedido.query",
        "ml_sync",
        "tn_sync",
        "wa_enviar",
        "requests.",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicios


def test_endpoints_namespaced():
    template = _leer(
        "templates/admin_crm.html"
    )
    base = _leer("templates/base.html")

    assert (
        "url_for('admin_crm.guardar')"
        in template
    )
    assert (
        "admin_crm_guardar"
        not in template
    )
    assert (
        "url_for('admin_crm.panel')"
        in base
    )


def test_blueprint_no_importa_modelos():
    rutas = _leer(
        "modules/admin/crm/routes.py"
    )

    assert "from models." not in rutas
    assert (
        'modelos = dependencias["modelos"]'
        in rutas
    )


def test_crm_mantiene_automatizaciones_bloqueadas():
    nucleo = _leer(
        "services/crm_nucleo.py"
    )

    assert (
        "def crm_habilita_automatizaciones("
        in nucleo
    )
    assert "return False" in nucleo
