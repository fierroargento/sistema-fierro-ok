"""Mapea insumos comprados a existencias sin generar movimientos."""

import json


def crear_mapeo(*, organizacion_id, unidad_negocio_id, insumo, existencia,
                MapeoInsumoInventario, db_session, usuario_id=None,
                observacion=None):
    if int(insumo.organizacion_id) != int(organizacion_id):
        raise ValueError("El insumo no pertenece al tenant activo.")
    if int(existencia.organizacion_id) != int(organizacion_id):
        raise ValueError("La existencia no pertenece al tenant activo.")
    mapeo = MapeoInsumoInventario(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        insumo_id=insumo.id,
        existencia_sucursal_id=existencia.id,
        activo=True,
        observacion=str(observacion or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(mapeo)
    db_session.commit()
    return mapeo


def habilitar_propuestas_stock(propuestas, mapeos, *, db_session):
    por_insumo = {int(item.insumo_id): item for item in mapeos if item.activo}
    habilitadas = []
    for propuesta in propuestas:
        if propuesta.tipo != "stock" or propuesta.estado != "bloqueada":
            continue
        detalle = json.loads(propuesta.detalle_json)
        insumo_id = detalle.get("insumo_id")
        mapeo = por_insumo.get(int(insumo_id)) if insumo_id is not None else None
        if mapeo is None:
            continue
        detalle.update({
            "existencia_sucursal_id": int(mapeo.existencia_sucursal_id),
            "mapeo_id": int(mapeo.id),
            "requiere_mapeo_item_inventario": False,
            "movimiento_creado": False,
        })
        propuesta.detalle_json = json.dumps(detalle, ensure_ascii=False, sort_keys=True)
        propuesta.estado = "preparada"
        propuesta.ejecutada = False
        habilitadas.append(propuesta)
    db_session.commit()
    return habilitadas
