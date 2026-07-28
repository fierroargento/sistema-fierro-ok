from pathlib import Path


def _bloque_sync_manual():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    inicio = app.index(
        "def ml_sync_manual("
    )
    fin = app.index(
        "\ndef ia_datos_detectados_pedido(",
        inicio,
    )
    return app[inicio:fin]


def test_sync_manual_recorre_cuentas_activas():
    bloque = _bloque_sync_manual()

    assert "cuentas_activas(" in bloque
    assert "for cuenta in cuentas:" in bloque
    assert "cuenta_ml=cuenta_actual" in bloque
    assert "cuenta_ml_actual()" not in bloque


def test_sync_manual_acumula_resultados():
    bloque = _bloque_sync_manual()

    for campo in (
        '"leidos"',
        '"creados"',
        '"actualizados"',
        '"omitidos"',
        '"cuentas_procesadas"',
        '"cuentas_fallidas"',
    ):
        assert campo in bloque

    assert (
        "ml_sync_mensajes_pendientes_pedidos()"
        in bloque
    )
    assert (
        "ml_sync_claims_pedidos_operativos()"
        in bloque
    )


def test_sync_manual_aisla_falla_por_cuenta():
    bloque = _bloque_sync_manual()

    assert "try:" in bloque
    assert "except Exception as error:" in bloque
    assert (
        'cuenta.last_sync_status = "error"'
        in bloque
    )
    compacto = "".join(bloque.split())
    assert (
        'resultado_total["cuentas_fallidas"]+=1'
        in compacto
    )


def test_panel_informa_cuentas_procesadas_y_fallidas():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def sync_mercadolibre("
    )
    fin = app.index(
        "\ndef reset_prueba_mercadolibre(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "Sync ML finalizada." in bloque
    assert "cuentas_procesadas" in bloque
    assert "cuentas_fallidas" in bloque
