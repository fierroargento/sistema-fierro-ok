from pathlib import Path


def _callback():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    inicio = contenido.index(
        "def callback_mercadolibre():"
    )
    fin = contenido.index(
        "\n\n@app.route",
        inicio,
    )

    return contenido[inicio:fin]


def test_callback_crea_vinculo_antes_commit():
    bloque = _callback()

    flush = bloque.index(
        "db.session.flush()"
    )
    vinculo = bloque.index(
        "asegurar_vinculo_ml_oauth("
    )
    commit = bloque.index(
        "db.session.commit()"
    )

    assert flush < vinculo < commit


def test_callback_usa_unidad_validada():
    bloque = _callback()

    assert (
        "unidad_oauth_callback"
        in bloque
    )
    assert (
        "membresia_oauth.organizacion"
        in bloque
    )
    assert (
        "VinculoCanalComercial"
        in bloque
    )


def test_callback_conserva_rollback():
    bloque = _callback()

    assert (
        "except Exception as error_callback:"
        in bloque
    )
    assert (
        "db.session.rollback()"
        in bloque
    )


def test_no_activa_vinculo_en_callback():
    bloque = _callback()

    assert (
        'estado="activo"'
        not in bloque
    )
    assert (
        'estado = "activo"'
        not in bloque
    )
