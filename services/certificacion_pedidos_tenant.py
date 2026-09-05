"""Certificación de solo lectura de la identidad SaaS de pedidos."""


def certificar_coleccion_pedidos_tenant(
    organizacion_id, pedidos, unidades,
):
    organizacion_id = int(organizacion_id)
    unidades_por_id = {
        int(unidad.id): int(unidad.organizacion_id)
        for unidad in unidades or []
    }
    conteos = {
        "pedidos_tenant": 0,
        "sin_organizacion": 0,
        "sin_unidad": 0,
        "unidad_inexistente": 0,
        "unidad_cruzada": 0,
    }
    hallazgos = []
    for pedido in pedidos or []:
        org_id = getattr(pedido, "organizacion_id", None)
        unidad_id = getattr(pedido, "unidad_negocio_id", None)
        if org_id is None:
            conteos["sin_organizacion"] += 1
            continue
        if int(org_id) != organizacion_id:
            continue
        conteos["pedidos_tenant"] += 1
        if unidad_id is None:
            conteos["sin_unidad"] += 1
            if len(hallazgos) < 100:
                hallazgos.append(f"Pedido #{pedido.id}: sin unidad de negocio.")
            continue
        unidad_org = unidades_por_id.get(int(unidad_id))
        if unidad_org is None:
            conteos["unidad_inexistente"] += 1
            if len(hallazgos) < 100:
                hallazgos.append(f"Pedido #{pedido.id}: unidad inexistente.")
        elif unidad_org != organizacion_id:
            conteos["unidad_cruzada"] += 1
            if len(hallazgos) < 100:
                hallazgos.append(f"Pedido #{pedido.id}: unidad de otro tenant.")

    bloqueos = []
    if conteos["sin_organizacion"]:
        bloqueos.append("Todavía existen pedidos legacy sin organización asignada.")
    if conteos["sin_unidad"]:
        bloqueos.append("Hay pedidos del tenant sin unidad de negocio.")
    if conteos["unidad_inexistente"]:
        bloqueos.append("Hay pedidos vinculados a unidades inexistentes.")
    if conteos["unidad_cruzada"]:
        bloqueos.append("Hay pedidos vinculados a unidades de otro tenant.")
    return {
        **conteos,
        "aprobada": not bloqueos,
        "bloqueos": bloqueos,
        "hallazgos": hallazgos,
        "hallazgos_limitados": len(hallazgos) >= 100,
        "escrituras_realizadas": 0,
        "integraciones_habilitables": False,
    }


def certificar_pedidos_tenant(organizacion_id, *, Pedido, UnidadNegocio):
    return certificar_coleccion_pedidos_tenant(
        organizacion_id,
        Pedido.query.order_by(Pedido.id.asc()).yield_per(500),
        UnidadNegocio.query.order_by(UnidadNegocio.id.asc()).all(),
    )
