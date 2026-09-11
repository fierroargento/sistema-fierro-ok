"""Alta transaccional interna desde expedientes TN; no usa conectores ni transporte."""

import json


def incorporar(lote, *, confirmacion, organizacion_id, unidad_negocio_id, usuario,
               Pedido, PedidoItem, ResultadoIncorporacionTiendaNube, db_session):
    if str(confirmacion or "").strip().upper() != "INCORPORAR":
        raise ValueError("Escribe INCORPORAR para confirmar el alta interna.")
    if lote is None or lote.organizacion_id != organizacion_id or lote.unidad_negocio_id != unidad_negocio_id:
        raise ValueError("El expediente no pertenece a la unidad activa.")
    if lote.estado != "certificado" or lote.puede_ejecutar:
        raise ValueError("Solo puede incorporarse un expediente certificado y sin permiso externo.")
    previo = ResultadoIncorporacionTiendaNube.query.filter_by(lote_id=lote.id).first()
    if previo is not None:
        return previo, False
    try:
        evidencia = json.loads(lote.evidencia_json)
    except (TypeError, ValueError) as error:
        raise ValueError("La evidencia certificada no es legible.") from error
    filas = evidencia.get("filas") or []
    if not filas or evidencia.get("firma_contenido") != lote.firma_contenido:
        raise ValueError("La evidencia no coincide con el expediente certificado.")

    preparados = []
    for fila in filas:
        if fila.get("bloqueos"):
            raise ValueError("El expediente contiene propuestas bloqueadas.")
        order_id = str(fila.get("order_id") or "").strip()
        existente = Pedido.query.filter_by(
            organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
            tn_cuenta_id=lote.tienda_nube_cuenta_id, tn_order_id=order_id,
        ).first()
        if existente is not None:
            raise ValueError(f"La orden {order_id} ya existe en el maestro interno.")
        snapshot = fila.get("snapshot") or {}
        items = snapshot.get("items") or []
        if not order_id or not items or any(item.get("estado") != "vinculado" or not item.get("producto_id") for item in items):
            raise ValueError("Una propuesta perdió la vinculación certificada de sus productos.")
        preparados.append((fila, snapshot, items))

    pedidos = []
    items_creados = 0
    try:
        for fila, snapshot, items in preparados:
            numero = str(fila.get("numero") or fila["order_id"])
            pedido = Pedido(
                organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
                origen="tiendanube_offline_certificado", canal="Tienda Nube",
                tn_cuenta_id=lote.tienda_nube_cuenta_id, tn_order_id=str(fila["order_id"]),
                tn_order_number=numero[:50], id_venta=str(fila["order_id"])[:50],
                tn_payment_status=str(snapshot.get("estado_pago") or "")[:50],
                cliente=(f"Cliente Tienda Nube {numero}")[:120], telefono="", mail="",
                estado="Cargando Pedido", contacto_iniciado=False,
                observaciones=f"Alta interna desde expediente certificado TN #{lote.id}. Revisar datos del cliente antes de operar.",
            )
            db_session.add(pedido)
            db_session.flush()
            for item in items:
                db_session.add(PedidoItem(
                    pedido_id=pedido.id, sku=str(item.get("sku") or "")[:50],
                    descripcion=str(item.get("nombre") or item.get("sku") or "Producto TN")[:200],
                    cantidad=int(item.get("cantidad") or 0),
                ))
                items_creados += 1
            pedidos.append(pedido)
        resultado = ResultadoIncorporacionTiendaNube(
            lote_id=lote.id, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
            pedidos_creados=len(pedidos), items_creados=items_creados, acciones_externas=0,
            pedido_ids_json=json.dumps([pedido.id for pedido in pedidos]),
            creado_por_usuario_id=getattr(usuario, "id", None), creado_por_username=getattr(usuario, "username", None),
        )
        db_session.add(resultado)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return resultado, True
