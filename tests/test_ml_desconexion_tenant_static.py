from pathlib import Path


def _bloque_desconexion():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    inicio = contenido.index(
        "def desconectar_mercadolibre("
    )
    fin = contenido.index(
        "\n\n@app.route(",
        inicio,
    )

    return contenido[inicio:fin]


def test_desconexion_exige_cuenta_del_tenant():
    bloque = _bloque_desconexion()

    assert (
        "resolver_tenant_usuario("
        in bloque
    )
    assert (
        "exigir_vinculo_cuenta_tenant("
        in bloque
    )
    assert (
        "CANAL_MERCADO_LIBRE"
        in bloque
    )
    assert (
        "VinculoCanalComercial"
        in bloque
    )
    assert "solo_activo=False" in bloque


def test_valida_tenant_antes_de_mutar():
    bloque = _bloque_desconexion()

    validacion = bloque.index(
        "exigir_vinculo_cuenta_tenant("
    )
    mutacion = bloque.index(
        'cuenta.estado_conexion = '
        '"desconectada"'
    )
    commit = bloque.index(
        "db.session.commit()"
    )

    assert validacion < mutacion < commit


def test_rechazo_no_modifica_cuenta():
    bloque = _bloque_desconexion()

    inicio = bloque.index(
        "except ValueError as error:"
    )
    fin = bloque.index(
        "identificacion = (",
        inicio,
    )
    rechazo = bloque[inicio:fin]

    assert (
        '"admin_integraciones.panel"'
        in rechazo
    )
    assert (
        "db.session.commit()"
        not in rechazo
    )
    assert (
        "cuenta.access_token = None"
        not in rechazo
    )


def test_no_quedan_endpoints_viejos():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    assert (
        '"admin_integraciones"'
        not in contenido
    )
    assert (
        '"admin_integraciones.panel"'
        in contenido
    )
