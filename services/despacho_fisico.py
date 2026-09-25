"""Reglas del pendiente físico para Mercado Envíos operado por Correo Argentino."""

from services.fechas import ahora_utc_naive


def es_mercado_envios_correo(pedido):
    """En Fierro, Mercado Envíos se controla operativamente por Correo Argentino."""
    if not pedido:
        return False

    canal = str(getattr(pedido, "canal", "") or "").strip().lower()
    tipo = str(getattr(pedido, "ml_tipo", "") or "").strip().lower()
    tipo = tipo.replace("í", "i")

    return canal == "mercado libre" and tipo == "mercado envios"


def puede_marcar_impuesto_sin_despacho(pedido):
    return bool(
        es_mercado_envios_correo(pedido)
        and getattr(pedido, "estado", None) == "Embalado"
        and not bool(getattr(pedido, "impuesto_sin_despacho", False))
    )


def tiene_despacho_fisico_pendiente(pedido):
    return bool(
        pedido
        and es_mercado_envios_correo(pedido)
        and bool(getattr(pedido, "impuesto_sin_despacho", False))
    )


def marcar_impuesto_sin_despacho(pedido, usuario="", fecha=None):
    if not puede_marcar_impuesto_sin_despacho(pedido):
        return False, "Este pedido no admite la marca Impuesto sin despacho."

    pedido.impuesto_sin_despacho = True
    pedido.impuesto_sin_despacho_fecha = fecha or ahora_utc_naive()
    pedido.impuesto_sin_despacho_usuario = str(usuario or "sistema")[:100]
    pedido.despacho_fisico_fecha = None
    pedido.despacho_fisico_usuario = None
    return True, "Pedido impuesto en Correo. Continúa pendiente de despacho físico."


def confirmar_despacho_fisico(pedido, usuario="", fecha=None):
    if not tiene_despacho_fisico_pendiente(pedido):
        return False, "El pedido no tiene un despacho físico pendiente."

    pedido.impuesto_sin_despacho = False
    pedido.despacho_fisico_fecha = fecha or ahora_utc_naive()
    pedido.despacho_fisico_usuario = str(usuario or "sistema")[:100]
    return True, "Despacho físico confirmado correctamente."
