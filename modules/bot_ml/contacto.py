"""
modules.bot_ml.contacto
-----------------------
Reglas simples de contacto inicial Mercado Libre / Acordas.

APB / SaaS:
- No envia mensajes.
- No escribe DB.
- No depende de Flask ni app.py.
- Solo genera textos y detecta productos para el flujo ML Acordas.
"""


def pedido_es_plegable_pp6040(pedido):
    """Detecta parrilla plegable para usar mensaje neutro ML Acordas."""
    if not pedido:
        return False

    for item in (getattr(pedido, "items", None) or []):
        sku = str(getattr(item, "sku", "") or "").upper()
        descripcion = str(getattr(item, "descripcion", "") or "").upper()

        if "PP6040" in sku or "PP6040" in descripcion or "PLEGABLE" in descripcion:
            return True

    return False


def generar_mensaje_contacto_ml(pedido, es_ml_acordas_entrega_fn):
    if not pedido or not es_ml_acordas_entrega_fn(pedido):
        return ""

    if pedido_es_plegable_pp6040(pedido):
        texto = (
            "Hola! Desde Fierro 100% Argento agradecemos tu compra.\n\n"
            "Tenes envio gratis, pero necesitamos coordinar para que llegue correctamente a destino.\n\n"
            "Por favor confirmanos:\n"
            "- Nombre completo de quien recibe\n"
            "- Documento\n"
            "- Direccion\n"
            "- Telefono de contacto\n\n"
            "Gracias! Quedamos atentos para continuar con el despacho."
        )
    else:
        texto = (
            "Hola! Desde Fierro 100% Argento agradecemos tu compra.\n\n"
            "Tu pedido tiene envio sin cargo con retiro en sucursal Via Cargo. Para coordinar correctamente, necesitamos que nos confirmes:\n\n"
            "- Nombre completo\n"
            "- Documento\n"
            "- Direccion\n"
            "- Telefono\n\n"
            "Con esto verificamos la sucursal mas cercana a tu domicilio.\n\n"
            "Gracias! Quedamos atentos."
        )

    if len(texto) > 348:
        texto = texto[:345] + "..."

    return texto