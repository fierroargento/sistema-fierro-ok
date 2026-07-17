"""
Normalización pura de datos recibidos desde Tienda Nube.

No usa Flask, base de datos ni realiza llamadas externas.
"""

from services.telefonos import normalizar_telefono_service


def extraer_telefono_tiendanube_service(order, telefono_actual=""):
    """Devuelve el primer teléfono disponible, normalizado para WhatsApp."""
    order = order if isinstance(order, dict) else {}
    customer = order.get("customer")

    if not isinstance(customer, dict):
        customer = {}

    telefono = (
        order.get("contact_phone")
        or customer.get("phone")
        or order.get("billing_phone")
        or telefono_actual
        or ""
    )

    return normalizar_telefono_service(telefono)
