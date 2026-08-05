from pathlib import Path


def _app():
    return Path(
        "app.py"
    ).read_text(encoding="utf-8")


def _bloque(nombre, siguiente):
    contenido = _app()

    inicio = contenido.index(
        f"def {nombre}("
    )
    fin = contenido.index(
        f"\ndef {siguiente}(",
        inicio,
    )

    return contenido[inicio:fin]


def test_nucleo_admite_cuentas_inyectadas():
    bloque = _bloque(
        "ml_sync_manual",
        "ia_datos_detectados_pedido",
    )

    assert "cuentas=None" in bloque
    assert "if cuentas is None:" in bloque
    assert "cuentas_activas(" in bloque
    assert (
        "cuentas = list(cuentas)"
        in bloque
    )


def test_fallback_global_permanece_intacto():
    bloque = _bloque(
        "ml_sync_manual",
        "ia_datos_detectados_pedido",
    )

    condicion = bloque.index(
        "if cuentas is None:"
    )
    consulta = bloque.index(
        "cuentas_activas("
    )
    inyectadas = bloque.index(
        "cuentas = list(cuentas)"
    )

    assert condicion < consulta < inyectadas


def test_ruta_resuelve_cuentas_del_tenant():
    bloque = _bloque(
        "sync_mercadolibre",
        "reset_prueba_mercadolibre",
    )

    assert (
        "resolver_tenant_usuario("
        in bloque
    )
    assert (
        "cuentas_mercado_libre_tenant("
        in bloque
    )
    assert (
        "VinculoCanalComercial"
        in bloque
    )
    assert "solo_activas=False" in bloque
    assert (
        "cuentas_activas("
        not in bloque
    )


def test_ruta_inyecta_solo_conectadas():
    bloque = _bloque(
        "sync_mercadolibre",
        "reset_prueba_mercadolibre",
    )

    assert (
        '"estado_conexion"'
        in bloque
    )
    assert (
        '== "conectada"'
        in bloque
    )
    assert "cuentas=cuentas" in bloque


def test_tenant_se_resuelve_antes_del_sync():
    bloque = _bloque(
        "sync_mercadolibre",
        "reset_prueba_mercadolibre",
    )

    tenant = bloque.index(
        "cuentas_mercado_libre_tenant("
    )
    llamada = bloque.index(
        "resultado = ml_sync_manual("
    )

    assert tenant < llamada
