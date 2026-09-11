"""Control final de solo lectura para pedidos TN incorporados internamente."""

import hashlib
import io
import json


def construir_control(resultado, pedidos, items, *, organizacion_id, unidad_negocio_id):
    if resultado is None or resultado.organizacion_id != organizacion_id or resultado.unidad_negocio_id != unidad_negocio_id:
        raise ValueError("El resultado no pertenece a la unidad activa.")
    try:
        esperados = [int(valor) for valor in json.loads(resultado.pedido_ids_json)]
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("El resultado no contiene identidades de pedidos legibles.") from error
    if not esperados or len(set(esperados)) != len(esperados):
        raise ValueError("El resultado contiene identidades vacías o duplicadas.")
    propios = [pedido for pedido in (pedidos or []) if pedido.organizacion_id == organizacion_id and pedido.unidad_negocio_id == unidad_negocio_id and pedido.id in esperados]
    por_id = {pedido.id: pedido for pedido in propios}
    items_por_pedido = {}
    for item in items or []:
        if item.pedido_id in por_id:
            items_por_pedido.setdefault(item.pedido_id, []).append(item)
    filas = []
    for pedido_id in esperados:
        pedido = por_id.get(pedido_id)
        bloqueos, pendientes = [], []
        if pedido is None:
            bloqueos.append("pedido_ausente_o_ajeno")
            filas.append({"pedido_id": pedido_id, "estado": "bloqueado", "bloqueos": bloqueos, "pendientes": [], "items": 0})
            continue
        if pedido.canal != "Tienda Nube" or pedido.origen != "tiendanube_offline_certificado":
            bloqueos.append("origen_inconsistente")
        if not str(pedido.tn_order_id or "").strip() or pedido.tn_cuenta_id is None:
            bloqueos.append("identidad_tienda_nube_incompleta")
        renglones = items_por_pedido.get(pedido.id, [])
        if not renglones:
            bloqueos.append("sin_items")
        if any(not str(item.sku or "").strip() or int(item.cantidad or 0) <= 0 for item in renglones):
            bloqueos.append("item_invalido")
        if not str(pedido.cliente or "").strip() or str(pedido.cliente).startswith("Cliente Tienda Nube "):
            pendientes.append("completar_cliente")
        if not str(pedido.telefono or "").strip():
            pendientes.append("completar_telefono")
        if not str(pedido.direccion or "").strip():
            pendientes.append("revisar_entrega")
        estado = "bloqueado" if bloqueos else "requiere_revision" if pendientes else "listo_revision_operativa"
        filas.append({
            "pedido_id": pedido.id, "order_id": pedido.tn_order_id, "numero": pedido.tn_order_number,
            "estado_pedido": pedido.estado, "estado": estado, "bloqueos": bloqueos,
            "pendientes": pendientes, "items": len(renglones),
        })
    ordenes = [fila.get("order_id") for fila in filas if fila.get("order_id")]
    duplicadas = sorted({orden for orden in ordenes if ordenes.count(orden) > 1})
    if duplicadas:
        for fila in filas:
            if fila.get("order_id") in duplicadas:
                fila["bloqueos"].append("orden_duplicada_en_resultado")
                fila["estado"] = "bloqueado"
    resumen = {
        "esperados": len(esperados), "encontrados": len(propios),
        "listos": sum(fila["estado"] == "listo_revision_operativa" for fila in filas),
        "requieren_revision": sum(fila["estado"] == "requiere_revision" for fila in filas),
        "bloqueados": sum(fila["estado"] == "bloqueado" for fila in filas),
        "items": sum(fila["items"] for fila in filas),
    }
    base = {"resultado_id": resultado.id, "lote_id": resultado.lote_id, "tenant": {"organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id}, "filas": filas, "resumen": resumen}
    firma = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return {**base, "firma_control": firma, "aprobado": not resumen["bloqueados"], "solo_lectura": True, "acciones_externas": 0, "escrituras": 0}


def exportar_control(control):
    return io.BytesIO(json.dumps(control, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
