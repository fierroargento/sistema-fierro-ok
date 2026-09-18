"""Prepara y decide propuestas de una recepción sin ejecutar sus efectos."""

import json

from services.fechas import ahora_utc_naive


def _crear(*, recepcion, item, tipo, detalle, estado, usuario_id,
           PropuestaImpactoCompra, db_session, existentes):
    sufijo = item.id if item is not None else "orden"
    clave = f"recepcion:{recepcion.id}:{tipo}:{sufijo}"
    if clave in existentes:
        return None
    propuesta = PropuestaImpactoCompra(
        organizacion_id=recepcion.organizacion_id,
        unidad_negocio_id=recepcion.unidad_negocio_id,
        recepcion_compra_id=recepcion.id,
        recepcion_item_id=getattr(item, "id", None),
        tipo=tipo, clave_idempotencia=clave, estado=estado,
        detalle_json=json.dumps(detalle, ensure_ascii=False, sort_keys=True),
        ejecutada=False, creado_por_usuario_id=usuario_id,
    )
    db_session.add(propuesta)
    existentes.add(clave)
    return propuesta


def preparar_propuestas(recepcion, *, organizacion_id, unidad_negocio_id,
                        PropuestaImpactoCompra, db_session, usuario_id=None,
                        mapeos=()):
    if int(recepcion.organizacion_id) != int(organizacion_id) or int(recepcion.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La recepción no pertenece al tenant y unidad activos.")
    if recepcion.estado not in {"preparatoria", "revisada"}:
        raise ValueError("La recepción no admite propuestas de impacto.")
    existentes = {
        item.clave_idempotencia
        for item in PropuestaImpactoCompra.query.filter_by(
            organizacion_id=organizacion_id,
            recepcion_compra_id=recepcion.id,
        ).all()
    }
    creadas = []
    mapeos_por_insumo = {
        int(item.insumo_id): item for item in mapeos if item.activo
    }
    for recibido in recepcion.items:
        orden_item = recibido.orden_item
        costo = _crear(
            recepcion=recepcion, item=recibido, tipo="costo",
            detalle={
                "insumo_id": orden_item.insumo_id,
                "precio_unitario_centavos": int(orden_item.precio_unitario_centavos),
                "proveedor_id": recepcion.orden.proveedor_id,
                "comprobante_referencia": recepcion.comprobante_referencia,
                "version_costo_creada": False,
            },
            estado="preparada" if orden_item.insumo_id else "bloqueada",
            usuario_id=usuario_id, PropuestaImpactoCompra=PropuestaImpactoCompra,
            db_session=db_session, existentes=existentes,
        )
        mapeo = mapeos_por_insumo.get(int(orden_item.insumo_id)) if orden_item.insumo_id else None
        stock = _crear(
            recepcion=recepcion, item=recibido, tipo="stock",
            detalle={
                "insumo_id": orden_item.insumo_id,
                "cantidad_recibida": str(recibido.cantidad_recibida),
                "requiere_mapeo_item_inventario": mapeo is None,
                "existencia_sucursal_id": getattr(mapeo, "existencia_sucursal_id", None),
                "mapeo_id": getattr(mapeo, "id", None),
                "movimiento_creado": False,
            },
            estado="preparada" if mapeo is not None else "bloqueada", usuario_id=usuario_id,
            PropuestaImpactoCompra=PropuestaImpactoCompra,
            db_session=db_session, existentes=existentes,
        )
        creadas.extend(item for item in (costo, stock) if item is not None)
    pagar = _crear(
        recepcion=recepcion, item=None, tipo="cuenta_pagar",
        detalle={
            "proveedor_id": recepcion.orden.proveedor_id,
            "importe_centavos": int(recepcion.orden.total_centavos),
            "comprobante_referencia": recepcion.comprobante_referencia,
            "obligacion_creada": False,
        },
        estado="preparada", usuario_id=usuario_id,
        PropuestaImpactoCompra=PropuestaImpactoCompra,
        db_session=db_session, existentes=existentes,
    )
    if pagar is not None:
        creadas.append(pagar)
    db_session.commit()
    return creadas


def decidir_propuesta(propuesta, decision, motivo, *, organizacion_id,
                      db_session, usuario_id=None):
    if int(propuesta.organizacion_id) != int(organizacion_id):
        raise ValueError("La propuesta no pertenece al tenant activo.")
    if propuesta.estado != "preparada":
        raise ValueError("Solo una propuesta preparada admite decisión.")
    if decision not in {"aprobar", "rechazar", "archivar"}:
        raise ValueError("La decisión no es válida.")
    if decision in {"rechazar", "archivar"} and not str(motivo or "").strip():
        raise ValueError("El motivo es obligatorio.")
    propuesta.estado = {
        "aprobar": "aprobada", "rechazar": "rechazada", "archivar": "archivada",
    }[decision]
    propuesta.motivo_decision = str(motivo or "").strip() or None
    propuesta.decidido_por_usuario_id = usuario_id
    propuesta.fecha_decision = ahora_utc_naive()
    propuesta.ejecutada = False
    db_session.commit()
    return propuesta


def leer_detalle(propuesta):
    return json.loads(propuesta.detalle_json)
