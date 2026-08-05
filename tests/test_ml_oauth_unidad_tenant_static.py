from pathlib import Path
import re


def _leer(nombre):
    return Path(nombre).read_text(
        encoding="utf-8"
    )


def _app():
    return _leer("app.py")


def _bloque(contenido, funcion):
    inicio = contenido.index(
        f"def {funcion}():"
    )
    fin = contenido.index(
        "\n\n@app.route",
        inicio,
    )
    return contenido[inicio:fin]


def test_registro_productivo_inyecta_unidades():
    app = _app()

    inicio = app.index(
        "crear_blueprint_integraciones("
    )
    fin = app.index(
        "\n)\n",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        '"UnidadNegocio": UnidadNegocio'
        in bloque
    )


def test_panel_lista_unidades_del_tenant():
    contenido = _leer(
        "modules/admin/integraciones/routes.py"
    )

    assert "UnidadNegocio.query" in contenido
    assert "organizacion.id" in contenido
    assert "activa=True" in contenido
    assert re.search(
        r"unidades_negocio\s*=\s*\(",
        contenido,
    )
    assert re.search(
        r"unidades_negocio\s*=\s*"
        r"\(\s*unidades_negocio\s*\)",
        contenido,
    )


def test_template_exige_unidad_para_oauth():
    contenido = _leer(
        "templates/admin_integraciones.html"
    )

    assert (
        'name="unidad_negocio_id"'
        in contenido
    )
    assert "required" in contenido
    assert (
        "Agregar cuenta Mercado Libre"
        in contenido
    )


def test_inicio_oauth_valida_unidad_tenant():
    bloque = _bloque(
        _app(),
        "conectar_mercadolibre",
    )

    assert "UnidadNegocio.query" in bloque
    assert "membresia_oauth" in bloque
    assert "activa=True" in bloque
    assert (
        '"ml_oauth_unidad_negocio_id"'
        in bloque
    )

    validacion = bloque.index(
        "unidad_oauth = ("
    )
    autorizacion = bloque.index(
        "params = urlencode("
    )

    assert validacion < autorizacion


def test_callback_revalida_unidad_antes_token():
    bloque = _bloque(
        _app(),
        "callback_mercadolibre",
    )

    assert (
        '"ml_oauth_unidad_negocio_id"'
        in bloque
    )
    assert (
        "unidad_negocio_id_esperada"
        in bloque
    )
    assert (
        "unidad_oauth_callback = ("
        in bloque
    )

    validacion = bloque.index(
        "unidad_oauth_callback = ("
    )
    token = bloque.index(
        "ml_exchange_code_for_token("
    )

    assert validacion < token


def test_oauth_no_crea_ni_activa_vinculo():
    app = _app()

    inicio = app.index(
        "def conectar_mercadolibre():"
    )
    inicio_callback = app.index(
        "def callback_mercadolibre():"
    )
    fin = app.index(
        "\n\n@app.route",
        inicio_callback,
    )
    bloque = app[inicio:fin]

    assert (
        "VinculoCanalComercial("
        not in bloque
    )
    assert (
        'estado="activo"'
        not in bloque
    )
