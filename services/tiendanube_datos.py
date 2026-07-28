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


def aplicar_destino_tiendanube_service(
    pedido,
    direccion,
    *,
    empresa="",
    tipo_entrega="",
):
    """
    Actualiza el destino importado desde Tienda Nube.

    Si el cliente ya confirmó una sucursal operativa,
    el re-sync no puede restaurar el domicilio de compra.
    """
    if not pedido:
        return False

    sucursal_confirmada = str(
        getattr(pedido, "sucursal_nombre", "")
        or ""
    ).strip()

    if sucursal_confirmada:
        return False

    direccion = dict(direccion or {})

    pedido.empresa_envio = (
        empresa
        or getattr(pedido, "empresa_envio", None)
    )
    pedido.tipo_entrega = (
        tipo_entrega
        or getattr(pedido, "tipo_entrega", None)
    )

    calle = str(
        direccion.get("direccion")
        or ""
    ).strip()
    codigo_postal = str(
        direccion.get("codigo_postal")
        or ""
    ).strip()
    localidad = str(
        direccion.get("localidad")
        or ""
    ).strip()
    provincia = str(
        direccion.get("provincia")
        or ""
    ).strip()

    if calle:
        pedido.direccion = calle[:200]
    if codigo_postal:
        pedido.codigo_postal = codigo_postal[:10]
    if localidad:
        pedido.localidad = localidad[:100]
    if provincia:
        pedido.provincia = provincia[:100]

    return True
