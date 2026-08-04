from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def _leer(ruta):
    return (
        RAIZ
        .joinpath(ruta)
        .read_text(encoding="utf-8")
    )


def test_inventario_usa_blueprint_modular():
    rutas = _leer(
        "modules/admin/inventario/routes.py"
    )

    assert "Blueprint(" in rutas
    assert (
        '"admin_inventario"'
        in rutas
    )
    assert (
        '"/admin/inventario"'
        in rutas
    )
    assert (
        '"/admin/inventario/guardar"'
        in rutas
    )


def test_panel_resuelve_tenant_y_rol_admin():
    rutas = _leer(
        "modules/admin/inventario/routes.py"
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
        "modules/admin/inventario/routes.py"
    )

    assert (
        "obtener_datos_panel_inventario("
        in rutas
    )
    assert ".query" not in rutas
    assert (
        '"admin_inventario.html"'
        in rutas
    )


def test_guardado_delega_y_hace_rollback():
    rutas = _leer(
        "modules/admin/inventario/routes.py"
    )

    assert (
        "procesar_accion_inventario_admin("
        in rutas
    )
    assert "db.session.rollback()" in rutas
    assert "registrar_auditoria(" in rutas
    assert (
        '"admin_inventario.panel"'
        in rutas
    )


def test_app_solo_compone_blueprint_inventario():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )
    bootstrap = Path(
        "services/bootstrap_modulos_web.py"
    ).read_text(encoding="utf-8")

    assert "registrar_modulos_web(" in app
    assert (
        "crear_blueprint_inventario("
        in bootstrap
    )
    assert "app.register_blueprint(" in bootstrap
    assert "def admin_inventario()" not in app
    assert (
        "def admin_inventario_guardar()"
        not in app
    )


def test_servicios_no_tocan_pedidos_o_canales():
    servicios = (
        _leer("services/inventario_admin.py")
        + _leer(
            "services/inventario_consultas.py"
        )
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


def test_template_declara_aislamiento():
    template = _leer(
        "templates/admin_inventario.html"
    )
    compacto = " ".join(
        template.split()
    )

    assert "no descuenta pedidos" in compacto
    assert "ni publica cantidades" in compacto
    assert (
        "sincronización con canales "
        "permanece bloqueada"
        in compacto
    )


def test_endpoints_namespaced_en_vistas():
    template = _leer(
        "templates/admin_inventario.html"
    )
    base = _leer("templates/base.html")

    assert (
        "url_for('admin_inventario.guardar')"
        in template
    )
    assert (
        "admin_inventario_guardar"
        not in template
    )
    assert (
        "url_for('admin_inventario.panel')"
        in base
    )


def test_blueprint_no_importa_modelos_concretos():
    rutas = _leer(
        "modules/admin/inventario/routes.py"
    )

    assert "from models." not in rutas
    assert (
        'modelos = dependencias["modelos"]'
        in rutas
    )
