"""Planifica pedidos desde lotes TN aprobados sin crear registros operativos."""

import hashlib
import io
import json


def _propios(registros, organizacion_id, unidad_negocio_id):
    return [
        registro for registro in (registros or [])
        if getattr(registro, "organizacion_id", None) == organizacion_id
        and getattr(registro, "unidad_negocio_id", None) == unidad_negocio_id
    ]


def _evidencia(lote):
    try:
        evidencia = json.loads(lote.evidencia_json or "{}")
    except (TypeError, ValueError) as error:
        raise ValueError("La evidencia del lote no es legible.") from error
    if not isinstance(evidencia.get("resultados"), list):
        raise ValueError("La evidencia del lote no contiene pedidos normalizados.")
    return evidencia


def preparar_plan(lote, pedidos_existentes, productos, *, organizacion_id, unidad_negocio_id):
    """Genera candidatos y bloqueos en memoria; nunca crea Pedido ni PedidoItem."""
    if lote is None or lote.organizacion_id != organizacion_id or lote.unidad_negocio_id != unidad_negocio_id:
        raise ValueError("El lote no pertenece a la unidad activa.")
    if lote.estado != "aprobado" or lote.puede_ejecutar:
        raise ValueError("El lote debe estar aprobado internamente y sin permiso de ejecucion.")
    evidencia = _evidencia(lote)
    pedidos = _propios(pedidos_existentes, organizacion_id, unidad_negocio_id)
    pedidos_por_id = {}
    for pedido in pedidos:
        clave = str(getattr(pedido, "tn_order_id", "") or "").strip()
        if clave:
            pedidos_por_id.setdefault(clave, []).append(pedido)
    productos_propios = [
        producto for producto in (productos or [])
        if getattr(producto, "organizacion_id", None) == organizacion_id
    ]
    productos_por_sku = {}
    for producto in productos_propios:
        sku = str(getattr(producto, "sku", "") or "").strip().upper()
        if sku:
            productos_por_sku.setdefault(sku, []).append(producto)

    filas = []
    for origen in evidencia["resultados"]:
        bloqueos = list(origen.get("bloqueos") or [])
        order_id = str(origen.get("order_id") or "").strip()
        if str(origen.get("store_id") or "") != str(lote.store_id_snapshot):
            bloqueos.append("store_inconsistente")
        existentes = pedidos_por_id.get(order_id, [])
        if existentes:
            bloqueos.append("pedido_existente" if len(existentes) == 1 else "pedido_duplicado_en_sistema")
        items = []
        for item in origen.get("productos") or []:
            sku = str(item.get("sku") or "").strip().upper()
            coincidencias = productos_por_sku.get(sku, [])
            estado = "vinculado" if len(coincidencias) == 1 else "sku_inexistente" if not coincidencias else "sku_ambiguo"
            if estado != "vinculado":
                bloqueos.append(estado)
            items.append({
                "sku": sku, "cantidad": int(item.get("cantidad") or 0),
                "nombre": item.get("nombre"), "estado": estado,
                "producto_id": coincidencias[0].id if len(coincidencias) == 1 else None,
            })
        bloqueos = list(dict.fromkeys(bloqueos))
        estado = "existente" if "pedido_existente" in bloqueos else "bloqueado" if bloqueos else "preparado"
        filas.append({
            "order_id": order_id, "numero": origen.get("numero"),
            "identidad": origen.get("identidad"), "estado": estado,
            "total_centavos": int(origen.get("total_centavos") or 0),
            "estado_pago": origen.get("estado_pago"),
            "telefono_presente": bool(origen.get("telefono_presente")),
            "items": items, "bloqueos": bloqueos,
            "crearia_pedido": estado == "preparado",
            "pedido_existente_id": existentes[0].id if len(existentes) == 1 else None,
        })
    resumen = {
        "filas": len(filas),
        "preparadas": sum(fila["estado"] == "preparado" for fila in filas),
        "existentes": sum(fila["estado"] == "existente" for fila in filas),
        "bloqueadas": sum(fila["estado"] == "bloqueado" for fila in filas),
        "items": sum(len(fila["items"]) for fila in filas),
        "acciones_externas": 0, "escrituras": 0,
    }
    base = {
        "tenant": {"organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id},
        "lote": {
            "id": lote.id, "store_id": lote.store_id_snapshot,
            "cuenta_id": lote.tienda_nube_cuenta_id,
            "huella_documento": lote.huella_documento,
        },
        "filas": filas, "resumen": resumen,
    }
    firma = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return {
        **base, "firma_plan": firma, "modo": "preparacion_pedidos_tienda_nube",
        "puede_aplicar": False, "acciones_externas": 0, "escrituras": 0,
    }


def exportar_plan(plan):
    return io.BytesIO(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
