from pathlib import Path


def _rutas():
    return Path(
        "modules/admin/integraciones/routes.py"
    ).read_text(encoding="utf-8")


def test_blueprint_conserva_url_del_panel():
    contenido = _rutas()

    assert (
        'Blueprint(\n'
        '        "admin_integraciones",'
        in contenido
    )
    assert (
        '@blueprint.route(\n'
        '        "/admin/integraciones",'
        in contenido
    )
    assert 'methods=["GET"]' in contenido
    assert "def panel():" in contenido


def test_panel_restringe_plataforma():
    contenido = _rutas()

    assert (
        "resolver_tenant_usuario("
        in contenido
    )
    assert (
        '"grupo-fierro"'
        in contenido
    )
    assert (
        'getattr(\n'
        '                membresia,\n'
        '                "rol",'
        in contenido
    )
    assert '!= "admin"' in contenido
    assert (
        'session.get(\n'
        '                    "organizacion_id"'
        in contenido
    )


def test_panel_consulta_cuentas_del_tenant():
    contenido = _rutas()

    assert (
        "cuentas_mercado_libre_tenant("
        in contenido
    )
    assert (
        "cuentas_tienda_nube_tenant("
        in contenido
    )
    assert (
        contenido.count(
            "solo_activas=False"
        )
        == 2
    )
    assert (
        "VinculoCanalComercial"
        in contenido
    )
    assert (
        "MercadoLibreCuenta.query"
        not in contenido
    )
    assert (
        "cuenta_tn_actual()"
        not in contenido
    )