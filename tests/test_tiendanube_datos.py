from services.tiendanube_datos import (
    extraer_telefono_tiendanube_service,
)


def test_tiendanube_normaliza_contact_phone_argentino():
    order = {
        "contact_phone": "011 15 5734-7193",
        "customer": {"phone": "2920123456"},
        "billing_phone": "2999999999",
    }

    assert (
        extraer_telefono_tiendanube_service(order)
        == "5491157347193"
    )


def test_tiendanube_usa_telefono_customer_como_fallback():
    order = {
        "contact_phone": "",
        "customer": {"phone": "01157347193"},
    }

    assert (
        extraer_telefono_tiendanube_service(order)
        == "5491157347193"
    )


def test_tiendanube_usa_billing_phone_como_fallback():
    order = {
        "customer": {},
        "billing_phone": "+54 9 011 5734-7193",
    }

    assert (
        extraer_telefono_tiendanube_service(order)
        == "5491157347193"
    )


def test_tiendanube_conserva_telefono_actual_si_no_llega_otro():
    assert (
        extraer_telefono_tiendanube_service(
            {},
            telefono_actual="5491157347193",
        )
        == "5491157347193"
    )


def test_resync_tn_preserva_sucursal_confirmada():
    from types import SimpleNamespace

    from services.tiendanube_datos import (
        aplicar_destino_tiendanube_service,
    )

    pedido = SimpleNamespace(
        sucursal_nombre="Agencia Palermo",
        empresa_envio="Vía Cargo",
        tipo_entrega="Sucursal",
        direccion="Guemes Nro.4326",
        codigo_postal="1425",
        localidad="Palermo",
        provincia="Capital Federal",
    )

    aplicado = aplicar_destino_tiendanube_service(
        pedido,
        {
            "direccion": (
                "Fray Justo Santamaria de Oro "
                "2663 Piso/Depto: 4C"
            ),
            "codigo_postal": "1425",
            "localidad": "Capital Federal",
            "provincia": "Capital Federal",
        },
        empresa="Vía Cargo",
        tipo_entrega="Sucursal",
    )

    assert aplicado is False
    assert pedido.sucursal_nombre == "Agencia Palermo"
    assert pedido.direccion == "Guemes Nro.4326"
    assert pedido.codigo_postal == "1425"
    assert pedido.localidad == "Palermo"
    assert pedido.provincia == "Capital Federal"
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"


def test_sync_tn_aplica_domicilio_si_no_hay_sucursal():
    from types import SimpleNamespace

    from services.tiendanube_datos import (
        aplicar_destino_tiendanube_service,
    )

    pedido = SimpleNamespace(
        sucursal_nombre="",
        empresa_envio="",
        tipo_entrega="",
        direccion="",
        codigo_postal="",
        localidad="",
        provincia="",
    )

    aplicado = aplicar_destino_tiendanube_service(
        pedido,
        {
            "direccion": "Domicilio comprador 123",
            "codigo_postal": "8500",
            "localidad": "Viedma",
            "provincia": "Rio Negro",
        },
        empresa="Correo Argentino",
        tipo_entrega="Domicilio",
    )

    assert aplicado is True
    assert pedido.direccion == "Domicilio comprador 123"
    assert pedido.codigo_postal == "8500"
    assert pedido.localidad == "Viedma"
    assert pedido.provincia == "Rio Negro"
    assert pedido.empresa_envio == "Correo Argentino"
    assert pedido.tipo_entrega == "Domicilio"


def test_app_delega_destino_tn_sin_pisarlo_directamente():
    from pathlib import Path

    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    inicio = app.index(
        "def tn_importar_o_actualizar_pedido("
    )
    fin = app.index(
        "\ndef tn_importar_pedido_por_id(",
        inicio,
    )
    bloque = app[inicio:fin]

    assert (
        "aplicar_destino_tiendanube_service("
        in bloque
    )
    assert (
        'pedido.direccion = direccion["direccion"]'
        not in bloque
    )
    assert (
        "pedido.codigo_postal = "
        'direccion["codigo_postal"]'
        not in bloque
    )
