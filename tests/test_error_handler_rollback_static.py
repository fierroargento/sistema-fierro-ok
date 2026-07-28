from pathlib import Path


def _app():
    return Path("app.py").read_text(
        encoding="utf-8-sig"
    )


def test_handler_500_revierte_antes_de_renderizar():
    app = _app()

    inicio = app.index(
        "def server_error("
    )
    fin = app.index(
        "\n@app.route(\"/login\"",
        inicio,
    )
    bloque = app[inicio:fin]

    indice_rollback = bloque.index(
        "db.session.rollback()"
    )
    indice_render = bloque.index(
        'render_template("500.html")'
    )

    assert indice_rollback < indice_render
    assert "[ERROR-500] Error original:" in bloque


def test_alertas_no_ocultan_error_de_base():
    app = _app()

    inicio = app.index(
        "def alertas_operativas("
    )
    fin = app.index(
        "\n\ndef ",
        inicio,
    )
    bloque = app[inicio:fin]

    assert "except Exception as error:" in bloque
    assert "db.session.rollback()" in bloque
    assert "[ALERTAS-OPERATIVAS]" in bloque
    assert "return []" in bloque


def test_inicio_revierte_si_falla_filtro_cross_sell():
    app = _app()

    inicio = app.index(
        "def inicio("
    )
    fin = app.index(
        "\n\n@app.route(\"/pedidos-preparacion\"",
        inicio,
    )
    bloque = app[inicio:fin]

    indice_except = bloque.index(
        "except Exception as e:"
    )
    bloque_error = bloque[indice_except:]

    indice_rollback = bloque_error.index(
        "db.session.rollback()"
    )
    indice_log = bloque_error.index(
        "[CROSS-SELL PREPARACION]"
    )

    assert indice_rollback < indice_log
