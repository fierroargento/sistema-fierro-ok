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
    """
    Detecta familia PP6040 usando solo SKU.

    APB:
    - La regla se centraliza en domain/productos.py.
    - No mira descripción ni observaciones.
    - PA9060H no entra como PP6040.
    """
    if not pedido:
        return False

    from domain.productos import pedido_tiene_pp6040
    return pedido_tiene_pp6040(pedido)


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
            "- Direccion completa\n"
            "- Localidad\n"
            "- Codigo postal\n"
            "- Telefono de contacto\n\n"
            "Gracias! Quedamos atentos para continuar con el despacho."
        )
    else:
        texto = (
            "Hola! Desde Fierro 100% Argento agradecemos tu compra.\n\n"
            "Tu pedido tiene envio sin cargo con retiro en sucursal Via Cargo. Para coordinar correctamente, necesitamos que nos confirmes:\n\n"
            "- Nombre completo\n"
            "- Documento\n"
            "- Direccion completa\n"
            "- Localidad\n"
            "- Codigo postal\n"
            "- Telefono\n\n"
            "Con esto verificamos la sucursal mas cercana a tu domicilio.\n\n"
            "Gracias! Quedamos atentos."
        )

    if len(texto) > 348:
        texto = texto[:345] + "..."

    return texto
