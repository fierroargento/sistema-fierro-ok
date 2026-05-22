import os


def ml_preparar_etiqueta_mercado_envios_service(
    order,
    shipment=None,
    ml_guardar_etiqueta_pdf=None,
):
    shipping = (order or {}).get("shipping") or {}
    shipment = shipment or {}

    shipping_id = str(
        shipping.get("id")
        or shipment.get("id")
        or ""
    ).strip()

    if not shipping_id:
        return ""

    nombre_pdf = ml_guardar_etiqueta_pdf(
        shipping_id
    )

    if not nombre_pdf:
        return ""

    return os.path.basename(
        str(nombre_pdf)
    )