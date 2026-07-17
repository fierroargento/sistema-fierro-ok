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
