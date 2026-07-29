from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def test_panel_estructura_es_exclusivo_de_admin():
    app = _app()

    inicio = app.index(
        "def admin_estructura("
    )
    fin = app.index(
        "\n\n@app.route(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert '@login_required' in app[
        app.rfind(
            "@app.route",
            0,
            inicio,
        ):inicio
    ]
    assert 'rol_actual() != "admin"' in bloque
    assert 'render_template(' in bloque
    assert '"admin_estructura.html"' in bloque


def test_guardado_admin_delega_en_servicio_y_revierte():
    app = _app()

    inicio = app.index(
        "def admin_estructura_guardar("
    )
    fin = app.index(
        "\n\n@app.route(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "procesar_accion_estructura_admin("
        in bloque
    )
    assert "db.session.rollback()" in bloque
    assert "registrar_auditoria(" in bloque


def test_panel_no_modifica_pedidos_ni_integraciones():
    servicio = Path(
        "services/estructura_admin.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "Pedido.query",
        "MercadoLibreCuenta",
        "TiendaNubeCuenta",
        "ml_sync",
        "tn_sync",
        "facturar_pedido",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_menu_admin_incluye_estructura():
    base = Path(
        "templates/base.html"
    ).read_text(encoding="utf-8-sig")

    assert (
        "url_for('admin_estructura')"
        in base
    )


def test_template_informa_aislamiento_productivo():
    template = Path(
        "templates/admin_estructura.html"
    ).read_text(encoding="utf-8")

    assert (
        "no se conectan automáticamente"
        in template
    )
    assert "estado_modulo" in template
    assert "crear_sucursal" in template
    assert "crear_entidad_fiscal" in template
    assert "crear_catalogo" in template
    assert "agregar_producto_catalogo" in template
