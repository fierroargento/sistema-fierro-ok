from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def test_panel_inventario_es_solo_admin():
    app = _app()
    inicio = app.index(
        "def admin_inventario("
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
    assert '"admin_inventario.html"' in bloque


def test_guardado_delega_y_hace_rollback():
    app = _app()
    inicio = app.index(
        "def admin_inventario_guardar("
    )
    fin = app.index(
        "\n\n@app.route(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "procesar_accion_inventario_admin("
        in bloque
    )
    assert "db.session.rollback()" in bloque
    assert "registrar_auditoria(" in bloque


def test_servicio_no_toca_pedidos_o_canales():
    servicio = Path(
        "services/inventario_admin.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "Pedido.query",
        "ml_sync",
        "tn_sync",
        "wa_enviar",
        "requests.",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_template_declara_aislamiento():
    template = Path(
        "templates/admin_inventario.html"
    ).read_text(encoding="utf-8")

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


def test_menu_incluye_inventario():
    base = Path(
        "templates/base.html"
    ).read_text(encoding="utf-8-sig")

    assert (
        "url_for('admin_inventario')"
        in base
    )
