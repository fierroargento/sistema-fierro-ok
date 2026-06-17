import json
import os


def ml_guardar_etiqueta_pdf_service(
    shipping_id,
    upload_folder,
    secure_filename_fn,
    ml_api_get_binario_fn,
    asegurar_pdf_local_desde_url_fn,
    logger_fn=None,
):
    """
    Descarga y guarda localmente la etiqueta PDF de Mercado Envíos.

    APB:
    - Este service no conoce Flask, app.config ni Mercado Libre directo.
    - Recibe dependencias inyectadas desde app.py para mantener bajo acoplamiento.
    - Devuelve el nombre del archivo local o None si no pudo descargarlo.
    """
    shipping_id = str(shipping_id or "").strip()
    if not shipping_id:
        return None

    os.makedirs(upload_folder, exist_ok=True)

    nombre_archivo = secure_filename_fn(f"ml_{shipping_id}.pdf")
    ruta_pdf = os.path.join(upload_folder, nombre_archivo)

    if os.path.exists(ruta_pdf) and os.path.getsize(ruta_pdf) > 0:
        return nombre_archivo

    intentos = [
        {"shipment_ids": shipping_id, "response_type": "pdf"},
        {"shipment_ids": shipping_id},
    ]

    for params in intentos:
        try:
            contenido, content_type = ml_api_get_binario_fn(
                "/shipment_labels",
                params=params,
                accept="application/pdf",
            )

            if contenido and (
                contenido[:4] == b"%PDF"
                or "pdf" in str(content_type).lower()
            ):
                with open(ruta_pdf, "wb") as salida:
                    salida.write(contenido)

                if os.path.exists(ruta_pdf) and os.path.getsize(ruta_pdf) > 0:
                    return nombre_archivo

            try:
                data = json.loads(contenido.decode("utf-8"))
                results = data.get("results") or []
                if results and results[0].get("url"):
                    nombre_descargado = asegurar_pdf_local_desde_url_fn(
                        results[0].get("url"),
                        prefijo="ml",
                    )
                    if nombre_descargado:
                        return os.path.basename(str(nombre_descargado))
            except Exception:
                pass

        except Exception as e:
            if logger_fn:
                logger_fn("No se pudo descargar etiqueta ML:", e)

    return None


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
