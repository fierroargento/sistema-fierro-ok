from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def test_panel_crm_es_solo_admin():
    app = _app()
    inicio = app.index(
        "def admin_crm("
    )
    bloque_previo = app[
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

    assert "@login_required" in bloque_previo
    assert 'rol_actual() != "admin"' in bloque
    assert '"admin_crm.html"' in bloque


def test_guardado_crm_delega_y_revierte():
    app = _app()
    inicio = app.index(
        "def admin_crm_guardar("
    )
    fin = app.index(
        "\n\n@app.route(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "procesar_accion_crm_admin("
        in bloque
    )
    assert "db.session.rollback()" in bloque
    assert "registrar_auditoria(" in bloque


def test_servicio_crm_no_opera_pedidos_o_canales():
    servicio = Path(
        "services/crm_admin.py"
    ).read_text(encoding="utf-8")

    prohibidos = [
        "Pedido.query",
        "ml_sync",
        "tn_sync",
        "wa_enviar",
        "facturar_pedido",
        "requests.",
    ]

    for prohibido in prohibidos:
        assert prohibido not in servicio


def test_template_advierte_aislamiento():
    template = Path(
        "templates/admin_crm.html"
    ).read_text(encoding="utf-8")

    assert "no importa pedidos" in template
    assert "no sincroniza canales" in template
    assert "no envía mensajes" in template


def test_menu_admin_incluye_crm():
    base = Path(
        "templates/base.html"
    ).read_text(encoding="utf-8-sig")

    assert "url_for('admin_crm')" in base
