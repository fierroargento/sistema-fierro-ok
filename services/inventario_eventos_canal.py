"""Contratos multicanal preparados; no están conectados a webhooks ni stock."""

from services.inventario_pedidos import agrupar_items_pedido


TIPOS_EVENTO = frozenset({
    "reservar", "liberar", "consumir", "revisar_devolucion",
})


def normalizar_cantidades(cantidades):
    normalizadas = {}
    if isinstance(cantidades, dict):
        pares = cantidades.items()
    else:
        pares = agrupar_items_pedido(cantidades).items()
    for sku, cantidad in pares:
        sku_normalizado = str(sku or "").strip().upper()
        try:
            cantidad_normalizada = int(cantidad or 0)
        except (TypeError, ValueError) as error:
            raise ValueError("Las cantidades del evento deben ser enteras.") from error
        if sku_normalizado and cantidad_normalizada > 0:
            normalizadas[sku_normalizado] = (
                normalizadas.get(sku_normalizado, 0) + cantidad_normalizada
            )
    if not normalizadas:
        raise ValueError("El evento no contiene cantidades inventariables.")
    return normalizadas


def crear_contrato_evento(
    *, canal, referencia, tipo_evento, cantidades, estado_origen="", parcial=False,
):
    tipo = str(tipo_evento or "").strip().lower()
    if tipo not in TIPOS_EVENTO:
        raise ValueError("El tipo de evento multicanal no es válido.")
    canal_normalizado = str(canal or "").strip().lower().replace(" ", "_")
    referencia_normalizada = str(referencia or "").strip()
    if not canal_normalizado or not referencia_normalizada:
        raise ValueError("El evento necesita canal y referencia externa.")
    cantidades_normalizadas = normalizar_cantidades(cantidades)
    return {
        "version": 1,
        "canal": canal_normalizado,
        "referencia": referencia_normalizada,
        "tipo_evento": tipo,
        "cantidades": cantidades_normalizadas,
        "parcial": bool(parcial),
        "estado_origen": str(estado_origen or "").strip().lower(),
        "requiere_revision": tipo == "revisar_devolucion",
        "modo": "desconectado",
    }


def contrato_desde_pedido(pedido, *, evento_externo=None, cantidades=None):
    """Traduce estados conocidos sin ejecutar el contrato resultante."""
    canal = str(getattr(pedido, "canal", "") or "").strip()
    estado = str(
        evento_externo
        or getattr(pedido, "estado", "")
        or ""
    ).strip().lower()
    if any(valor in estado for valor in ("cancel", "anulad")):
        tipo = "liberar"
    elif any(valor in estado for valor in ("devol", "return", "refund")):
        tipo = "revisar_devolucion"
    elif any(valor in estado for valor in ("despach", "shipped", "fulfilled")):
        tipo = "consumir"
    else:
        tipo = "reservar"
    referencia = (
        getattr(pedido, "id_venta", None)
        or getattr(pedido, "ml_pack_id", None)
        or getattr(pedido, "tn_order_id", None)
        or getattr(pedido, "id", None)
    )
    return crear_contrato_evento(
        canal=canal,
        referencia=referencia,
        tipo_evento=tipo,
        cantidades=cantidades if cantidades is not None else getattr(pedido, "items", ()),
        estado_origen=estado,
        parcial=cantidades is not None,
    )


def contrato_puede_ejecutarse(contrato, configuracion):
    """Permanece falso mientras el adaptador esté desconectado de producción."""
    return bool(
        contrato
        and contrato.get("modo") == "productivo"
        and str(getattr(configuracion, "estado", "")) == "activo"
    )
