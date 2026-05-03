"""
modules/whatsapp/cross_sell.py
───────────────────────────────
Maneja el flujo de venta de productos adicionales por WhatsApp.
Se activa después de confirmar la sucursal, antes del despacho.
"""

from .config import CATALOGO, CROSS_SELL_POR_SKU, ALIAS_PAGO
from .sender import wa_enviar_texto, wa_enviar_producto


def obtener_skus_pedido(pedido):
    """Devuelve lista de SKUs del pedido en mayúsculas."""
    skus = []
    for item in (pedido.items or []):
        sku = str(getattr(item, "sku", "") or "").upper().strip()
        if sku:
            skus.append(sku)
    return skus


def obtener_productos_a_ofrecer(pedido):
    """
    Devuelve lista ordenada de SKUs a ofrecer según lo que compró el cliente.
    Evita duplicados si compró varios productos.
    """
    skus_comprados = obtener_skus_pedido(pedido)
    productos = []
    vistos = set()

    for sku in skus_comprados:
        for sku_ofrecer in CROSS_SELL_POR_SKU.get(sku, []):
            if sku_ofrecer not in vistos:
                vistos.add(sku_ofrecer)
                productos.append(sku_ofrecer)

    return productos


def hay_cross_sell(pedido):
    """Devuelve True si hay productos para ofrecer a este cliente."""
    return bool(obtener_productos_a_ofrecer(pedido))


def wa_ofrecer_producto(telefono, sku_producto):
    """
    Manda el mensaje de oferta de un producto específico.
    Si tiene imagen la incluye, si no solo texto.
    """
    producto = CATALOGO.get(sku_producto)
    if not producto:
        return False

    return wa_enviar_producto(
        telefono,
        producto["descripcion"],
        producto.get("imagen_url", ""),
    )


def wa_responder_precio(telefono, sku_producto, cantidad=1):
    """
    Manda precio + alias cuando el cliente pregunta o confirma interés.
    """
    producto = CATALOGO.get(sku_producto)
    if not producto:
        return False

    precio_total = producto["precio"] * cantidad
    cantidad_str = f"{cantidad} unidad{'es' if cantidad > 1 else ''}"

    texto = (
        f"*{producto['nombre']}*\n\n"
        f"Precio: *${precio_total:,.0f}* ({cantidad_str})\n\n"
        f"Para confirmar tu compra podés hacer la transferencia al alias:\n"
        f"💳 *{ALIAS_PAGO}*\n\n"
        f"Avisanos cuando hagas el pago y coordinamos el envío junto con tu parrilla 😊"
    )

    return wa_enviar_texto(telefono, texto)


def wa_cerrar_cross_sell(telefono):
    """Mensaje de cierre cuando el cliente no quiere nada o se agotaron los productos."""
    return wa_enviar_texto(
        telefono,
        "¡Perfecto! Cuando despachemos tu pedido te avisamos por acá con el número de seguimiento 😊"
    )


def wa_escalar_venta_cerrada(pedido, sku_producto, cantidad, operador_notificado=False):
    """
    Cuando el cliente confirmó que quiere comprar, escala al operador
    con el contexto de la venta cerrada para que confirme el pago.
    """
    try:
        from app import db
        producto = CATALOGO.get(sku_producto, {})
        precio_total = producto.get("precio", 0) * cantidad
        resumen = (
            f"VENTA CERRADA WA: {producto.get('nombre', sku_producto)} "
            f"x{cantidad} = ${precio_total:,.0f} | Alias: {ALIAS_PAGO}"
        )
        resumen_actual = (pedido.ia_resumen or "").strip()
        pedido.ia_resumen = f"{resumen_actual} | {resumen}".strip(" |")
        pedido.ml_mensajes_pendientes = True
        pedido.ia_requiere_operador = True
        db.session.commit()
        print(f"[WA CROSS-SELL] Pedido #{pedido.id} — {resumen}")
    except Exception as e:
        print("[WA CROSS-SELL] Error escalando venta:", e)
