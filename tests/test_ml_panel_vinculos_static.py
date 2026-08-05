from pathlib import Path


def _leer(nombre):
    return Path(nombre).read_text(
        encoding="utf-8"
    )


def _funcion_app(nombre):
    contenido = _leer("app.py")
    inicio = contenido.index(
        f"def {nombre}():"
    )
    fin = contenido.index(
        "\n\n@app.route",
        inicio,
    )
    return contenido[inicio:fin]


def test_panel_conserva_vinculos_ml():
    contenido = _leer(
        "modules/admin/integraciones/routes.py"
    )

    assert (
        "obtener_vinculos_canal_tenant("
        in contenido
    )
    assert (
        "canal=CANAL_MERCADO_LIBRE"
        in contenido
    )
    assert "solo_activos=False" in contenido
    assert (
        "vinculos_ml=vinculos_ml"
        in contenido
    )


def test_boton_sync_exige_vinculo_activo():
    contenido = _leer(
        "modules/admin/integraciones/routes.py"
    )

    inicio = contenido.index(
        "hay_cuentas_ml_activas = any("
    )
    fin = contenido.index(
        "ultimos_logs_tn = (",
        inicio,
    )
    bloque = contenido[inicio:fin]

    assert '"estado"' in bloque
    assert '== "activo"' in bloque
    assert (
        "vinculo.mercado_libre_cuenta"
        in bloque
    )
    assert '== "conectada"' in bloque


def test_sync_manual_solo_usa_vinculos_activos():
    bloque = _funcion_app(
        "sync_mercadolibre"
    )

    assert "solo_activas=True" in bloque
    assert "solo_activas=False" not in bloque
    assert (
        "ml_sync_manual("
        in bloque
    )


def test_template_muestra_estado_y_unidad():
    contenido = _leer(
        "templates/admin_integraciones.html"
    )

    assert "<th>V?nculo</th>" in contenido
    assert "<th>Unidad</th>" in contenido
    assert (
        "{% for vinculo in vinculos_ml %}"
        in contenido
    )
    assert (
        "vinculo.unidad_negocio.nombre"
        in contenido
    )
    assert "vinculo.estado" in contenido


def test_no_cambia_webhooks_ni_scheduler():
    contenido = _leer("app.py")

    assert (
        "def webhook_mercadolibre("
        in contenido
    )
    assert (
        "def callback_mercadolibre("
        in contenido
    )
