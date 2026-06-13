"""
modules.bot_ml.links
--------------------
Helpers puros para links operativos de Mercado Libre.

APB / SaaS:
- No consulta API.
- No escribe DB.
- No depende de Flask ni app.py.
- Solo arma URLs a partir de datos del pedido.
"""


def ml_link_detalle_venta(pedido):
    if not pedido:
        return ""

    if getattr(pedido, "canal", None) != "Mercado Libre":
        return ""

    id_venta = str(getattr(pedido, "id_venta", "") or "").strip()
    if not id_venta:
        return ""

    return f"https://www.mercadolibre.com.ar/ventas/{id_venta}/detalle"


def ml_link_chat_venta(pedido):
    if not pedido:
        return ""

    if getattr(pedido, "canal", None) != "Mercado Libre":
        return ""

    # El chat de ML puede requerir pack_id en lugar del ID de venta.
    # El detalle de venta sigue usando id_venta; la mensajeria usa ml_pack_id con fallback a id_venta.
    id_chat = str(
        getattr(pedido, "ml_pack_id", None)
        or getattr(pedido, "id_venta", None)
        or ""
    ).strip()

    if not id_chat:
        return ""

    return (
        f"https://www.mercadolibre.com.ar/ventas/nueva/mensajeria/{id_chat}"
        "?source=ml&callbackWording=Ventas"
        "&callbackUrl=https%3A%2F%2Fwww.mercadolibre.com.ar%2Fventas%2Fomni%2Flistado"
    )