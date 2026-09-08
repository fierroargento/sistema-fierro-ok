"""Certificación de solo lectura de la identidad SaaS de WhatsApp."""


def certificar_coleccion_whatsapp_tenant(
    organizacion_id, mensajes, unidades, pedidos,
):
    organizacion_id = int(organizacion_id)
    unidades_por_id = {
        int(unidad.id): int(unidad.organizacion_id)
        for unidad in unidades or []
    }
    pedidos_por_id = {
        int(pedido.id): int(pedido.organizacion_id)
        for pedido in pedidos or []
        if getattr(pedido, "organizacion_id", None) is not None
    }
    conteos = {
        "mensajes_tenant": 0,
        "sin_organizacion": 0,
        "sin_unidad": 0,
        "unidad_inexistente": 0,
        "unidad_cruzada": 0,
        "pedido_cruzado": 0,
    }
    hallazgos = []

    def registrar(clave, mensaje):
        conteos[clave] += 1
        if len(hallazgos) < 100:
            hallazgos.append(mensaje)

    for mensaje in mensajes or []:
        org_id = getattr(mensaje, "organizacion_id", None)
        unidad_id = getattr(mensaje, "unidad_negocio_id", None)
        if org_id is None:
            registrar(
                "sin_organizacion",
                f"Mensaje #{mensaje.id}: sin organización.",
            )
            continue
        if int(org_id) != organizacion_id:
            continue
        conteos["mensajes_tenant"] += 1
        if unidad_id is None:
            registrar(
                "sin_unidad",
                f"Mensaje #{mensaje.id}: sin unidad de negocio.",
            )
        else:
            unidad_org = unidades_por_id.get(int(unidad_id))
            if unidad_org is None:
                registrar(
                    "unidad_inexistente",
                    f"Mensaje #{mensaje.id}: unidad inexistente.",
                )
            elif unidad_org != organizacion_id:
                registrar(
                    "unidad_cruzada",
                    f"Mensaje #{mensaje.id}: unidad de otro tenant.",
                )
        pedido_id = getattr(mensaje, "pedido_id", None)
        if pedido_id is not None:
            pedido_org = pedidos_por_id.get(int(pedido_id))
            if pedido_org is not None and pedido_org != organizacion_id:
                registrar(
                    "pedido_cruzado",
                    f"Mensaje #{mensaje.id}: pedido de otro tenant.",
                )

    etiquetas = {
        "sin_organizacion": "Existen mensajes legacy sin organización asignada.",
        "sin_unidad": "Hay mensajes del tenant sin unidad de negocio.",
        "unidad_inexistente": "Hay mensajes vinculados a unidades inexistentes.",
        "unidad_cruzada": "Hay mensajes vinculados a unidades de otro tenant.",
        "pedido_cruzado": "Hay mensajes vinculados a pedidos de otro tenant.",
    }
    bloqueos = [
        texto for clave, texto in etiquetas.items() if conteos[clave]
    ]
    return {
        **conteos,
        "aprobada": not bloqueos,
        "bloqueos": bloqueos,
        "hallazgos": hallazgos,
        "hallazgos_limitados": len(hallazgos) >= 100,
        "escrituras_realizadas": 0,
        "integraciones_habilitables": False,
    }


def certificar_whatsapp_tenant(
    organizacion_id, *, WhatsAppMensaje, UnidadNegocio, Pedido,
):
    return certificar_coleccion_whatsapp_tenant(
        organizacion_id,
        WhatsAppMensaje.query.order_by(
            WhatsAppMensaje.id.asc(),
        ).yield_per(500),
        UnidadNegocio.query.order_by(UnidadNegocio.id.asc()).all(),
        Pedido.query.order_by(Pedido.id.asc()).yield_per(500),
    )
