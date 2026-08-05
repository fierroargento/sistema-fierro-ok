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


def test_inicio_oauth_guarda_tenant():
    bloque = _bloque(
        "conectar_mercadolibre",
        "callback_mercadolibre",
    )

    assert (
        "resolver_tenant_usuario("
        in bloque
    )
    assert (
        'session["ml_oauth_state"]'
        in bloque
    )
    assert (
        'session["ml_oauth_organizacion_id"]'
        in bloque
    )
    assert (
        "membresia_oauth.organizacion_id"
        in bloque
    )


def test_callback_consume_state_y_tenant():
    bloque = _bloque(
        "callback_mercadolibre",
        "desconectar_mercadolibre",
    )

    assert (
        'session.pop("ml_oauth_state"'
        in bloque
    )
    assert (
        'session.pop(\n'
        '        "ml_oauth_organizacion_id"'
        in bloque
    )
    assert (
        "organizacion_id_esperada is None"
        in bloque
    )


def test_callback_exige_mismo_tenant():
    bloque = _bloque(
        "callback_mercadolibre",
        "desconectar_mercadolibre",
    )

    assert (
        "resolver_tenant_usuario("
        in bloque
    )
    assert (
        "membresia_oauth.organizacion_id"
        in bloque
    )
    assert (
        "!= organizacion_id_esperada"
        in bloque
    )


def test_tenant_se_valida_antes_del_token():
    bloque = _bloque(
        "callback_mercadolibre",
        "desconectar_mercadolibre",
    )

    validacion = bloque.index(
        "!= organizacion_id_esperada"
    )
    intercambio = bloque.index(
        "ml_exchange_code_for_token("
    )
    guardado = bloque.index(
        "ml_guardar_token_en_cuenta("
    )

    assert (
        validacion
        < intercambio
        < guardado
    )


def test_callback_no_crea_vinculo_todavia():
    bloque = _bloque(
        "callback_mercadolibre",
        "desconectar_mercadolibre",
    )

    assert (
        "VinculoCanalComercial("
        not in bloque
    )
    assert (
        "mercado_libre_cuenta_id="
        not in bloque
    )
