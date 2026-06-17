import json
import os


def etiqueta_archivo_local_disponible_service(
    etiqueta_archivo,
    upload_folder,
):
    archivo = os.path.basename(str(etiqueta_archivo or ""))
    if not archivo:
        return False

    return os.path.exists(
        os.path.join(upload_folder, archivo)
    )


def ml_guardar_etiqueta_pdf_service(
    shipping_id,
    upload_folder,
    secure_filename_fn,
    ml_api_get_binario_fn,
    asegurar_pdf_local_desde_url_fn,
    logger_fn=None,
):
    """
    Descarga y guarda localmente la etiqueta PDF de Mercado Envios.

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


def ml_asegurar_etiqueta_disponible_service(
    pedido,
    es_mercado_envios_fn,
    etiqueta_archivo_local_disponible_fn,
    ml_obtener_order_fn,
    ml_guardar_etiqueta_pdf_fn,
):
    """
    Garantiza que la etiqueta ML esta disponible en el servidor actual.

    APB:
    - Mantiene las mutaciones sobre pedido concentradas en una regla testeable.
    - No conoce Flask, db ni app.config.
    - Las funciones externas se inyectan desde app.py.
    """
    if not pedido or not es_mercado_envios_fn(pedido):
        return True

    etiqueta_archivo = getattr(pedido, "etiqueta_archivo", None)
    if etiqueta_archivo and str(etiqueta_archivo).startswith("http"):
        return True

    if etiqueta_archivo_local_disponible_fn(etiqueta_archivo):
        return True

    if not getattr(pedido, "ml_shipping_id", None) and getattr(pedido, "id_venta", None):
        order = ml_obtener_order_fn(pedido.id_venta)
        shipment_id = (order.get("shipping") or {}).get("id") if order else ""
        if shipment_id:
            pedido.ml_shipping_id = str(shipment_id).strip()

    if getattr(pedido, "ml_shipping_id", None):
        nombre_pdf = ml_guardar_etiqueta_pdf_fn(pedido.ml_shipping_id)
        if nombre_pdf:
            pedido.etiqueta_archivo = os.path.basename(str(nombre_pdf))
            return etiqueta_archivo_local_disponible_fn(pedido.etiqueta_archivo)

    return False


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
