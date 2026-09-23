from pathlib import Path


def _app():
    return Path("app.py").read_text(encoding="utf-8-sig")


def _bloque(texto, inicio, fin):
    desde = texto.index(inicio)
    return texto[desde:texto.index(fin, desde)]


def test_backfill_ml_solo_toca_pedidos_de_la_organizacion_de_la_cuenta():
    bloque = _bloque(
        _app(), "def backfill_ml_identidad_cuenta_pedidos():",
        "\ndef asegurar_columnas_integracion_tn():",
    )
    assert 'organizacion_id = getattr(cuenta, "organizacion_id", None)' in bloque
    assert "Pedido.organizacion_id == int(organizacion_id)" in bloque
    assert "not organizacion_id" in bloque


def test_auxiliares_ml_exigen_y_filtran_organizacion():
    app = _app()
    mensajes = _bloque(
        app, "def ml_sync_mensajes_pendientes_pedidos(organizacion_id):",
        "\ndef ml_pedido_tiene_mensajes_pendientes(",
    )
    claims = _bloque(
        app, "def ml_sync_claims_pedidos_operativos(organizacion_id):",
        "\ndef ml_pedido_tiene_claim(",
    )
    assert "Pedido.organizacion_id == int(organizacion_id)" in mensajes
    assert "organizacion_id=organizacion_id" in claims
    assert "ml_sync_mensajes_pendientes_pedidos(organizacion_id)" in app
    assert "ml_sync_claims_pedidos_operativos(organizacion_id)" in app


def test_reset_ml_compatibilidad_no_borra_otro_tenant():
    bloque = _bloque(
        _app(), "def reset_ml_directo():", "\n\n\n@app.route(\"/historico\")",
    )
    assert "membresia = membresia_actual()" in bloque
    assert "Pedido.organizacion_id == membresia.organizacion_id" in bloque


def test_devoluciones_y_reclamos_delegan_validacion_integral():
    app = _app()
    devolucion = _bloque(
        app, "def gestionar_devolucion(id):",
        "\n@app.route(\"/pedido/<int:id>/cerrar-reclamo-ml-devolucion\"",
    )
    reclamo = _bloque(
        app, "def cerrar_reclamo_ml_devolucion(id):",
        "\n\n    \n@app.route(\"/pedido/<int:id>/revisar-reclamo\"",
    )
    assert "validar_devolucion_pedido(" in devolucion
    assert "validar_cierre_reclamo_ml(" in reclamo
