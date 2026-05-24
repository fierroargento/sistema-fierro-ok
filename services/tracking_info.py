def tracking_info_pedido_service(pedido):
    """
    Devuelve acceso rápido al seguimiento del pedido.

    Regla APB:
    - Andreani y Vía Cargo abren directo el seguimiento.
    - Correo Argentino no tiene URL directa confiable: copia el seguimiento y abre el formulario correcto.
    - Mercado Envíos se trata como Correo ML aunque empresa_envio venga guardada como "Mercado Envíos".
    """

    if not pedido:
        return None

    seguimiento = str(
        getattr(pedido, "seguimiento", None)
        or getattr(pedido, "tn_tracking_number", None)
        or ""
    ).strip()

    tn_url = str(
        getattr(pedido, "tn_tracking_url", None)
        or ""
    ).strip()

    if not seguimiento and not tn_url:
        return None

    if tn_url:
        return {
            "url": tn_url,
            "copiar": False,
            "seguimiento": seguimiento,
            "titulo": "Abrir seguimiento de Tienda Nube",
        }

    transporte = str(
        getattr(pedido, "empresa_envio", None)
        or ""
    ).strip().lower()

    tipo_ml = str(
        getattr(pedido, "ml_tipo", None)
        or ""
    ).strip().lower()

    es_mercado_envios = (
        "mercado envios" in tipo_ml
        or "mercado envíos" in tipo_ml
        or "mercado envios" in transporte
        or "mercado envíos" in transporte
    )

    if es_mercado_envios:
        return {
            "url": "https://www.correoargentino.com.ar/formularios/mercadolibre",
            "copiar": True,
            "seguimiento": seguimiento,
            "titulo": "Copiar seguimiento y abrir Correo Argentino Mercado Libre",
        }

    if "andreani" in transporte:
        return {
            "url": f"https://www.andreani.com/envio/{seguimiento}",
            "copiar": False,
            "seguimiento": seguimiento,
            "titulo": "Abrir seguimiento Andreani",
        }

    if "via cargo" in transporte or "vía cargo" in transporte:
        return {
            "url": f"https://viacargo.com.ar/seguimiento-de-envio/{seguimiento}/",
            "copiar": False,
            "seguimiento": seguimiento,
            "titulo": "Abrir seguimiento Via Cargo",
        }

    if "correo" in transporte:
        return {
            "url": "https://www.correoargentino.com.ar/formularios/e-commerce",
            "copiar": True,
            "seguimiento": seguimiento,
            "titulo": "Copiar seguimiento y abrir Correo Argentino e-commerce",
        }

    return None