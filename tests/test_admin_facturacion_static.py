from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def test_panel_facturacion_es_solo_admin():
    app = _app()
    inicio = app.index(
        "def admin_facturacion("
    )
    previo = app[
        app.rfind(
            "@app.route",
            0,
            inicio,
        ):inicio
    ]
    fin = app.index(
        "\n\n@app.route(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "@login_required" in previo
    assert 'rol_actual() != "admin"' in bloque
    assert '"admin_facturacion.html"' in bloque


def test_guardado_fiscal_delega_y_revierte():
    app = _app()
    inicio = app.index(
        "def admin_facturacion_guardar("
    )
    fin = app.index(
        "\n\n@app.route(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "procesar_accion_facturacion_admin("
        in bloque
    )
    assert "db.session.rollback()" in bloque
    assert "registrar_auditoria(" in bloque


def test_servicio_no_emite_ni_importa_pedidos():
    servicio = Path(
        "services/facturacion_admin.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "Pedido.query",
        "requests.",
        "pyafip",
        "wsfe",
        "solicitar_cae",
        "facturar_pedido",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_template_declara_bloqueo_real():
    template = Path(
        "templates/admin_facturacion.html"
    ).read_text(encoding="utf-8")

    compacto = " ".join(
        template.split()
    )

    assert "No existe todavía conexión con ARCA" in compacto
    assert "emisión real está bloqueada por código" in compacto


def test_menu_incluye_facturacion():
    base = Path(
        "templates/base.html"
    ).read_text(encoding="utf-8-sig")

    assert (
        "url_for('admin_facturacion')"
        in base
    )
