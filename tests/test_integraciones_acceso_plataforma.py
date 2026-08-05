from pathlib import Path


def _bloque_acceso():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    inicio = contenido.index(
        "def puede_administrar_integraciones():"
    )
    fin = contenido.index(
        "\n\ndef tn_store_id():",
        inicio,
    )

    return contenido[inicio:fin]


def test_integraciones_exige_admin():
    bloque = _bloque_acceso()

    assert (
        'rol_actual() != "admin"'
        in bloque
    )
    assert "return False" in bloque


def test_integraciones_resuelve_tenant_autorizado():
    bloque = _bloque_acceso()

    assert "resolver_tenant_usuario(" in bloque
    assert "usuario_actual()" in bloque
    assert "UsuarioOrganizacion" in bloque
    assert (
        'session.get(\n'
        '                "organizacion_id"'
        in bloque
    )


def test_integraciones_restringida_a_plataforma():
    bloque = _bloque_acceso()

    assert '"grupo-fierro"' in bloque
    assert (
        'getattr(\n'
        '            organizacion,\n'
        '            "slug"'
        in bloque
    )


def test_todas_las_acciones_usan_la_guardia():
    contenido = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    acciones = (
        "admin_integraciones",
        "test_tiendanube",
        "sync_tiendanube",
        "registrar_webhooks_tiendanube",
        "reset_prueba_tiendanube",
        "conectar_mercadolibre",
        "callback_mercadolibre",
        "desconectar_mercadolibre",
        "sync_mercadolibre",
        "reset_prueba_mercadolibre",
        "reset_total_mercadolibre",
    )

    for posicion, accion in enumerate(
        acciones
    ):
        inicio = contenido.index(
            f"def {accion}("
        )

        if posicion + 1 < len(acciones):
            siguiente = acciones[
                posicion + 1
            ]
            fin = contenido.index(
                f"def {siguiente}(",
                inicio,
            )
        else:
            fin = contenido.index(
                "\n\n@app.route",
                inicio,
            )

        bloque = contenido[inicio:fin]

        assert (
            "puede_administrar_integraciones()"
            in bloque
        ), accion
