"""
modules/whatsapp/cross_sell.py
───────────────────────────────
Cross-sell APB basado en catálogo dinámico.
Lee productos e imágenes desde static/catalogo/.
"""

import json
from pathlib import Path

from .config import ALIAS_PAGO
from .sender import wa_enviar_texto, wa_enviar_producto


BASE_DIR = Path(__file__).resolve().parents[2]

CATALOGO_PATH = BASE_DIR / "static" / "catalogo" / "catalogo_config.json"
PRODUCTOS_DIR = BASE_DIR / "static" / "catalogo" / "productos"


def cargar_catalogo():
    try:
        with open(CATALOGO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("productos", {})

    except Exception as e:
        print("[CATALOGO] Error cargando catálogo:", e)
        return {}


def obtener_producto(sku):
    catalogo = cargar_catalogo()

    producto = catalogo.get(sku.upper())
    if not producto:
        return None

    producto = producto.copy()

    ruta_imagen = PRODUCTOS_DIR / sku.upper() / "wa.jpg"

    if ruta_imagen.exists():
        producto["imagen_url"] = (
            f"/static/catalogo/productos/{sku.upper()}/wa.jpg"
        )
    else:
        producto["imagen_url"] = ""

    return producto


def obtener_skus_pedido(pedido):
    """Devuelve lista de SKUs del pedido."""
    skus = []

    for item in (pedido.items or []):
        sku = str(getattr(item, "sku", "") or "").upper().strip()

        if sku:
            skus.append(sku)

    return skus


def obtener_productos_a_ofrecer(pedido):
    """
    Devuelve SKUs de cross-sell
    según productos comprados.
    """

    catalogo = cargar_catalogo()

    productos = []
    vistos = set()

    for sku in obtener_skus_pedido(pedido):

        producto = catalogo.get(sku)
        if not producto:
            continue

        upsells = producto.get("upsells", [])

        for upsell in upsells:

            sku_ofrecer = upsell.get("sku", "").upper()

            if not sku_ofrecer:
                continue

            if sku_ofrecer in vistos:
                continue

            vistos.add(sku_ofrecer)
            productos.append(sku_ofrecer)

    return productos


def hay_cross_sell(pedido):
    return bool(obtener_productos_a_ofrecer(pedido))


def wa_ofrecer_producto(telefono, sku_producto):

    producto = obtener_producto(sku_producto)

    if not producto:
        return False

    return wa_enviar_producto(
        telefono,
        producto.get("descripcion", producto.get("nombre", "")),
        producto.get("imagen_url", ""),
    )


def wa_responder_precio(telefono, sku_producto, cantidad=1):

    producto = obtener_producto(sku_producto)

    if not producto:
        return False

    precio = producto.get("precio", 0)

    precio_total = precio * cantidad

    cantidad_str = f"{cantidad} unidad{'es' if cantidad > 1 else ''}"

    texto = (
        f"*{producto.get('nombre', sku_producto)}*\n\n"
        f"Precio: *${precio_total:,.0f}* ({cantidad_str})\n\n"
        f"Para confirmar tu compra podés transferir al alias:\n"
        f"💳 *{ALIAS_PAGO}*\n\n"
        f"Avisanos cuando hagas el pago 😊"
    )

    return wa_enviar_texto(telefono, texto)


def wa_cerrar_cross_sell(telefono):

    return wa_enviar_texto(
        telefono,
        "¡Perfecto! Cuando despachemos tu pedido te avisamos por acá con el seguimiento 😊"
    )


def wa_escalar_venta_cerrada(
    pedido,
    sku_producto,
    cantidad,
    operador_notificado=False
):

    try:
        from app import db

        producto = obtener_producto(sku_producto) or {}

        precio_total = producto.get("precio", 0) * cantidad

        resumen = (
            f"VENTA CERRADA WA: "
            f"{producto.get('nombre', sku_producto)} "
            f"x{cantidad} = ${precio_total:,.0f}"
        )

        resumen_actual = (pedido.ia_resumen or "").strip()

        pedido.ia_resumen = (
            f"{resumen_actual} | {resumen}"
        ).strip(" |")

        pedido.ml_mensajes_pendientes = True
        pedido.ia_requiere_operador = True

        db.session.commit()

        print(f"[WA CROSS-SELL] Pedido #{pedido.id} — {resumen}")

    except Exception as e:
        print("[WA CROSS-SELL] Error:", e)