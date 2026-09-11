"""Certifica expedientes TN locales sin crear pedidos ni ejecutar transporte."""

import hashlib
import io
import json


def _snapshot(propuesta):
    try:
        datos = json.loads(propuesta.snapshot_json)
    except (TypeError, ValueError) as error:
        raise ValueError("Una propuesta contiene evidencia ilegible.") from error
    if str(datos.get("order_id") or "") != str(propuesta.tn_order_id):
        raise ValueError("Una propuesta no coincide con su identidad congelada.")
    return datos


def certificar(propuestas, pedidos_existentes, *, organizacion_id, unidad_negocio_id):
    seleccion = list(propuestas or [])
    if not seleccion:
        raise ValueError("Selecciona propuestas aprobadas para certificar.")
    cuentas = set()
    filas = []
    existentes = {
        str(getattr(pedido, "tn_order_id", "") or "")
        for pedido in (pedidos_existentes or [])
        if getattr(pedido, "organizacion_id", None) == organizacion_id
        and getattr(pedido, "unidad_negocio_id", None) == unidad_negocio_id
    }
    for propuesta in seleccion:
        if propuesta.organizacion_id != organizacion_id or propuesta.unidad_negocio_id != unidad_negocio_id:
            raise ValueError("Una propuesta pertenece a otro tenant.")
        if propuesta.estado != "aprobada" or propuesta.puede_crear_pedido:
            raise ValueError("Todas las propuestas deben estar aprobadas y bloqueadas para ejecución.")
        cuentas.add(propuesta.tienda_nube_cuenta_id)
        datos = _snapshot(propuesta)
        bloqueos = ["pedido_existente"] if str(propuesta.tn_order_id) in existentes else []
        filas.append({
            "propuesta_id": propuesta.id, "order_id": propuesta.tn_order_id,
            "numero": propuesta.tn_order_number, "snapshot": datos,
            "total_centavos": int(datos.get("total_centavos") or 0), "bloqueos": bloqueos,
        })
    if len(cuentas) != 1:
        raise ValueError("Un expediente solo puede contener una cuenta Tienda Nube.")
    base = {
        "tenant": {"organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id},
        "cuenta_id": next(iter(cuentas)), "filas": sorted(filas, key=lambda fila: fila["order_id"]),
    }
    firma = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    bloqueadas = sum(bool(fila["bloqueos"]) for fila in filas)
    return {
        **base, "firma_contenido": firma,
        "estado": "certificado" if not bloqueadas else "observado",
        "resumen": {"propuestas": len(filas), "bloqueadas": bloqueadas, "total_centavos": sum(fila["total_centavos"] for fila in filas)},
        "puede_ejecutar": False, "pedidos_creados": 0, "acciones_externas": 0,
    }


def guardar(certificacion, *, usuario, LoteIncorporacionTiendaNube, ItemLoteIncorporacionTiendaNube, EventoLoteIncorporacionTiendaNube, db_session):
    tenant = certificacion["tenant"]
    existente = LoteIncorporacionTiendaNube.query.filter_by(
        organizacion_id=tenant["organizacion_id"], unidad_negocio_id=tenant["unidad_negocio_id"],
        firma_contenido=certificacion["firma_contenido"],
    ).first()
    if existente is not None:
        return existente, False
    lote = LoteIncorporacionTiendaNube(
        organizacion_id=tenant["organizacion_id"], unidad_negocio_id=tenant["unidad_negocio_id"],
        tienda_nube_cuenta_id=certificacion["cuenta_id"], firma_contenido=certificacion["firma_contenido"],
        evidencia_json=json.dumps(certificacion, ensure_ascii=False, sort_keys=True),
        propuestas=certificacion["resumen"]["propuestas"], total_centavos=certificacion["resumen"]["total_centavos"],
        estado=certificacion["estado"], puede_ejecutar=False,
        observaciones="Contiene pedidos existentes" if certificacion["resumen"]["bloqueadas"] else None,
        creado_por_usuario_id=getattr(usuario, "id", None), creado_por_username=getattr(usuario, "username", None),
    )
    try:
        db_session.add(lote)
        db_session.flush()
        for fila in certificacion["filas"]:
            db_session.add(ItemLoteIncorporacionTiendaNube(
                lote_id=lote.id, propuesta_id=fila["propuesta_id"], organizacion_id=lote.organizacion_id,
                unidad_negocio_id=lote.unidad_negocio_id, tn_order_id=fila["order_id"],
                snapshot_json=json.dumps(fila["snapshot"], ensure_ascii=False, sort_keys=True),
            ))
        db_session.add(EventoLoteIncorporacionTiendaNube(
            lote_id=lote.id, organizacion_id=lote.organizacion_id, unidad_negocio_id=lote.unidad_negocio_id,
            estado_nuevo=lote.estado, detalle="Expediente certificado sin ejecución", username=getattr(usuario, "username", None),
        ))
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return lote, True


def exportar(lote, *, organizacion_id, unidad_negocio_id):
    if lote is None or lote.organizacion_id != organizacion_id or lote.unidad_negocio_id != unidad_negocio_id:
        raise ValueError("El expediente no pertenece a la unidad activa.")
    datos = json.loads(lote.evidencia_json)
    datos["control"] = {"lote_id": lote.id, "estado": lote.estado, "puede_ejecutar": False, "pedidos_creados": 0, "acciones_externas": 0}
    return io.BytesIO(json.dumps(datos, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
