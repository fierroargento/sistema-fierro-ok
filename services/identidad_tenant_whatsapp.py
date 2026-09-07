"""Diagnóstico offline de identidad tenant para mensajes WhatsApp existentes."""


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def diagnosticar_identidad_tenant_whatsapp(mensajes, pedidos):
    """Clasifica candidatos por pedido asociado sin escribir ni inferir por teléfono."""
    pedidos_por_id = {
        _entero(getattr(pedido, "id", None)): pedido
        for pedido in pedidos or []
        if _entero(getattr(pedido, "id", None)) is not None
    }
    conteos = {
        "asignados": 0,
        "inferibles_por_pedido": 0,
        "pendientes": 0,
        "conflictos": 0,
    }
    detalle = []
    for mensaje in mensajes or []:
        explicita = (
            _entero(getattr(mensaje, "organizacion_id", None)),
            _entero(getattr(mensaje, "unidad_negocio_id", None)),
        )
        pedido = pedidos_por_id.get(_entero(getattr(mensaje, "pedido_id", None)))
        candidata = (
            _entero(getattr(pedido, "organizacion_id", None)),
            _entero(getattr(pedido, "unidad_negocio_id", None)),
        ) if pedido is not None else (None, None)

        if explicita[0] is not None and candidata[0] is not None and explicita != candidata:
            estado = "conflicto"
        elif explicita[0] is not None:
            estado = "asignado"
        elif candidata[0] is not None:
            estado = "inferible_por_pedido"
        else:
            estado = "pendiente"
        conteos[{"asignado": "asignados", "inferible_por_pedido": "inferibles_por_pedido", "pendiente": "pendientes", "conflicto": "conflictos"}[estado]] += 1
        if estado != "asignado" and len(detalle) < 100:
            detalle.append({
                "mensaje_id": getattr(mensaje, "id", None),
                "pedido_id": getattr(mensaje, "pedido_id", None),
                "estado": estado,
                "candidata": candidata,
            })

    bloqueos = []
    if conteos["inferibles_por_pedido"]:
        bloqueos.append("Hay mensajes atribuibles por pedido que requieren aprobación.")
    if conteos["pendientes"]:
        bloqueos.append("Hay mensajes sin identidad tenant demostrable.")
    if conteos["conflictos"]:
        bloqueos.append("Hay mensajes cuya identidad contradice la del pedido.")
    return {
        **conteos,
        "total": sum(conteos.values()),
        "detalle": detalle,
        "detalle_limitado": True,
        "aprobada": not bloqueos,
        "bloqueos": bloqueos,
        "escrituras_realizadas": 0,
        "integraciones_habilitables": False,
    }


def obtener_diagnostico_identidad_tenant_whatsapp(*, WhatsAppMensaje, Pedido):
    return diagnosticar_identidad_tenant_whatsapp(
        WhatsAppMensaje.query.order_by(WhatsAppMensaje.id.asc()).yield_per(500),
        Pedido.query.order_by(Pedido.id.asc()).yield_per(500),
    )
