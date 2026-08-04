from pathlib import Path


def _routes():
    return Path(
        "modules/admin/estructura/routes.py"
    ).read_text(encoding="utf-8")


def test_panel_estructura_es_blueprint_tenant():
    routes = _routes()

    assert 'Blueprint(' in routes
    assert '"admin_estructura"' in routes
    assert 'resolver_tenant_usuario(' in routes
    assert 'membresia.rol != "admin"' in routes
    assert 'session["organizacion_id"]' in routes
    assert '@blueprint.route("/admin/estructura")' in routes
    assert (
        '"/admin/estructura/guardar"'
        in routes
    )


def test_guardado_delega_y_revierte():
    routes = _routes()

    assert (
        "procesar_accion_estructura_admin("
        in routes
    )
    assert "db.session.rollback()" in routes
    assert "registrar_auditoria(" in routes


def test_app_solo_registra_blueprint():
    app = Path("app.py").read_text(
        encoding="utf-8"
    )
    bootstrap = Path(
        "services/bootstrap_modulos_web.py"
    ).read_text(encoding="utf-8")

    assert "registrar_modulos_web(" in app
    assert (
        "crear_blueprint_estructura("
        in bootstrap
    )
    assert "app.register_blueprint(" in bootstrap
    assert "def admin_estructura(" not in app
    assert (
        "def admin_estructura_guardar("
        not in app
    )
    assert (
        '@app.route("/admin/estructura")'
        not in app
    )


def test_consultas_panel_filtran_tenant():
    consultas = Path(
        "services/estructura_consultas.py"
    ).read_text(encoding="utf-8")

    assert consultas.count(
        "organizacion_id=organizacion_id"
    ) >= 5
    assert (
        "Catalogo.organizacion_id"
        in consultas
    )
    assert ".outerjoin(" in consultas
    assert "VinculoCanalComercial.id.is_(None)" in consultas


def test_panel_no_ejecuta_operacion_productiva():
    contenidos = (
        Path(
            "services/estructura_admin.py"
        ).read_text(encoding="utf-8"),
        Path(
            "services/estructura_consultas.py"
        ).read_text(encoding="utf-8"),
        _routes(),
    )

    prohibidos = (
        "Pedido.query",
        "ml_sync",
        "tn_sync",
        "facturar_pedido",
        "ml_upsert_pedido",
        "tn_importar_o_actualizar_pedido",
    )

    for contenido in contenidos:
        for prohibido in prohibidos:
            assert prohibido not in contenido


def test_menu_y_template_usan_blueprint():
    base = Path(
        "templates/base.html"
    ).read_text(encoding="utf-8-sig")
    template = Path(
        "templates/admin_estructura.html"
    ).read_text(encoding="utf-8")

    assert (
        "url_for('admin_estructura.panel')"
        in base
    )
    assert (
        "url_for('admin_estructura.guardar')"
        in template
    )
    assert "admin_estructura_guardar" not in template
    assert (
        "no se conectan automaticamente"
        in template.lower()
        or "no se conectan autom" in template.lower()
    )


def test_template_conserva_acciones():
    template = Path(
        "templates/admin_estructura.html"
    ).read_text(encoding="utf-8")

    for accion in (
        "estado_modulo",
        "crear_sucursal",
        "crear_entidad_fiscal",
        "crear_catalogo",
        "agregar_producto_catalogo",
        "crear_vinculo_canal",
        "estado_vinculo_canal",
    ):
        assert accion in template
