from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def test_panel_carga_cuentas_del_tenant():
    rutas = Path(
        "modules/admin/integraciones/routes.py"
    ).read_text(encoding="utf-8")

    assert (
        "cuentas_mercado_libre_tenant("
        in rutas
    )
    assert (
        "cuentas_tienda_nube_tenant("
        in rutas
    )
    assert "solo_activas=False" in rutas
    assert (
        "VinculoCanalComercial"
        in rutas
    )
    assert (
        "MercadoLibreCuenta.query"
        not in rutas
    )
    assert (
        "cuenta_tn_actual()"
        not in rutas
    )

    app = _app()

    assert (
        "def admin_integraciones("
        not in app
    )
    assert (
        "crear_blueprint_integraciones("
        in app
    )


def test_oauth_usa_state_y_token_nuevo():
    app = _app()

    inicio = app.index(
        "def conectar_mercadolibre("
    )
    fin = app.index(
        "\ndef desconectar_mercadolibre(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert 'session["ml_oauth_state"]' in bloque
    assert '"state": oauth_state' in bloque
    assert 'session.pop("ml_oauth_state"' in bloque
    assert "estado_recibido != estado_esperado" in bloque
    assert "ml_api_get_con_token(" in bloque
    assert "access_token," in bloque
    assert "ml_obtener_usuario_actual()" not in bloque


def test_callback_reconecta_por_seller_id():
    app = _app()

    inicio = app.index(
        "def callback_mercadolibre("
    )
    fin = app.index(
        "\n\n@app.route(\n"
        '    "/admin/integraciones/mercadolibre/"',
        inicio,
    )
    bloque = app[inicio:fin]

    assert ".filter_by(user_id_ml=seller_id)" in bloque
    assert "cuenta_nueva = cuenta is None" in bloque
    assert "MercadoLibreCuenta(" in bloque
    assert "cuenta_ml_actual()" not in bloque


def test_desconexion_es_logica_y_por_id():
    app = _app()

    inicio = app.index(
        "def desconectar_mercadolibre("
    )
    fin = app.index(
        "\n\n@app.route("
        "\"/admin/integraciones/mercadolibre/sync\"",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "desconectar_mercadolibre(cuenta_id)"
        in bloque
    )
    assert "query.get_or_404(" in bloque
    assert (
        'estado_conexion = "desconectada"'
        in bloque
    )
    assert "access_token = None" in bloque
    assert "refresh_token = None" in bloque
    assert "db.session.delete(" not in bloque

def test_template_lista_y_acciona_por_cuenta():
    template = Path(
        "templates/admin_integraciones.html"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert "{% for cuenta in cuentas_ml %}" in template
    assert "cuenta_id=cuenta.id" in template
    assert "Agregar cuenta Mercado Libre" in template
    assert "Sincronizar todas las cuentas ML" in template
    assert "cuenta_ml." not in template
