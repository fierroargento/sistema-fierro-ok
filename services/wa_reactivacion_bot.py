"""
services.wa_reactivacion_bot
----------------------------
Reglas APB para reactivar el bot WhatsApp despues de takeover operador.

APB / SaaS:
- No escribe DB.
- No envia mensajes.
- No depende de Flask ni app.py.
- Solo decide wa_estado y estado_conversacional.
"""


def _normalizar_estado(valor):
    return str(valor or "").strip().lower()


def decidir_reactivacion_bot_wa(pedido):
    """
    Decide a que flujo vuelve el bot cuando el operador lo reactiva.

    Problema que evita:
    - No mandar siempre a "esperando_datos" / "recolectando_datos".
    - Si el pedido estaba en cross-sell, debe volver a cross_sell.
    - Si ya tenia datos completos/despacho, debe volver a despacho_en_proceso.
    """
    wa_estado_actual = _normalizar_estado(getattr(pedido, "wa_estado", ""))

    if wa_estado_actual == "cross_sell":
        return {
            "wa_estado": "cross_sell",
            "estado_conversacional": "cross_sell",
            "motivo": "reactivar_cross_sell",
        }

    if wa_estado_actual == "cross_sell_cerrado":
        return {
            "wa_estado": "cross_sell_cerrado",
            "estado_conversacional": "cross_sell_cerrado",
            "motivo": "reactivar_cross_sell_cerrado",
        }

    if wa_estado_actual in {
        "despacho_en_proceso",
        "confirmado_cliente",
        "falta_elegir_transporte",
        "esperando_confirmacion_sucursal",
    }:
        return {
            "wa_estado": wa_estado_actual,
            "estado_conversacional": "datos_completos",
            "motivo": "reactivar_despacho",
        }

    if wa_estado_actual in {
        "despachado",
        "listo_para_retirar",
        "postventa",
        "finalizado",
    }:
        return {
            "wa_estado": wa_estado_actual,
            "estado_conversacional": wa_estado_actual,
            "motivo": "reactivar_estado_operativo",
        }

    return {
        "wa_estado": "esperando_datos",
        "estado_conversacional": "recolectando_datos",
        "motivo": "reactivar_recoleccion",
    }