"""Control con huella y de solo lectura del circuito preparatorio de compras."""

import hashlib
import io
import json
from decimal import Decimal, ROUND_HALF_UP


def controlar_compras(*, organizacion_id, unidad_negocio_id, ordenes,
                      recepciones, facturas, mapeos, propuestas):
    hallazgos = []
    huellas_factura = set()
    mapeos_activos = {int(item.insumo_id) for item in mapeos if item.activo}

    for orden in ordenes:
        calculado = sum(int(item.subtotal_centavos) for item in orden.items)
        if calculado != int(orden.total_centavos):
            hallazgos.append({"codigo": "total_orden_inconsistente", "orden_id": orden.id})
        for item in orden.items:
            recibido = sum(
                Decimal(str(linea.cantidad_recibida))
                for recepcion in orden.recepciones if recepcion.estado != "anulada"
                for linea in recepcion.items if linea.orden_compra_item_id == item.id
            )
            if recibido > Decimal(str(item.cantidad)):
                hallazgos.append({"codigo": "cantidad_sobre_recibida", "orden_item_id": item.id})

    for recepcion in recepciones:
        if getattr(recepcion, "impacta_stock", False) or getattr(recepcion, "impacta_costos", False):
            hallazgos.append({"codigo": "recepcion_con_impacto_indebido", "recepcion_id": recepcion.id})
        calculado = sum(
            int((Decimal(str(item.cantidad_recibida)) * Decimal(int(item.orden_item.precio_unitario_centavos))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            for item in recepcion.items
        )
        if calculado != int(recepcion.subtotal_centavos):
            hallazgos.append({"codigo": "subtotal_recepcion_inconsistente", "recepcion_id": recepcion.id})

    for factura in facturas:
        clave = (factura.proveedor_id, factura.tipo_comprobante, factura.punto_venta, factura.numero)
        if clave in huellas_factura:
            hallazgos.append({"codigo": "factura_duplicada", "factura_id": factura.id})
        huellas_factura.add(clave)
        if factura.estado == "conciliada" and int(factura.diferencia_centavos) != 0:
            hallazgos.append({"codigo": "factura_conciliada_con_diferencia", "factura_id": factura.id})
        if factura.impacta_fiscal or factura.obligacion_creada:
            hallazgos.append({"codigo": "factura_con_impacto_indebido", "factura_id": factura.id})

    for propuesta in propuestas:
        if propuesta.ejecutada:
            hallazgos.append({"codigo": "propuesta_ejecutada", "propuesta_id": propuesta.id})
        if propuesta.tipo in {"stock", "costo"}:
            insumo_id = getattr(propuesta.recepcion_item.orden_item, "insumo_id", None)
            if propuesta.tipo == "stock" and propuesta.estado != "bloqueada" and insumo_id not in mapeos_activos:
                hallazgos.append({"codigo": "stock_sin_mapeo", "propuesta_id": propuesta.id})

    resultado = {
        "organizacion_id": organizacion_id,
        "unidad_negocio_id": unidad_negocio_id,
        "modo": "solo_lectura",
        "aprobado": not hallazgos and not any(item.estado == "observada" for item in facturas),
        "resumen": {
            "ordenes": len(ordenes), "recepciones": len(recepciones),
            "facturas": len(facturas),
            "facturas_observadas": sum(item.estado == "observada" for item in facturas),
            "mapeos_activos": sum(bool(item.activo) for item in mapeos),
            "propuestas": len(propuestas), "hallazgos": len(hallazgos),
        },
        "hallazgos": hallazgos,
        "alcance": "Consistencia de registros preparatorios y sus indicadores; no consulta movimientos ni sistemas externos.",
        "controles": {
            "escrituras": 0,
            "propuestas_ejecutadas": sum(bool(item.ejecutada) for item in propuestas),
            "recepciones_con_indicador_stock": sum(bool(getattr(item, "impacta_stock", False)) for item in recepciones),
            "recepciones_con_indicador_costos": sum(bool(getattr(item, "impacta_costos", False)) for item in recepciones),
            "obligaciones_indicadas_en_facturas": sum(bool(item.obligacion_creada) for item in facturas),
            "impactos_fiscales_indicados_en_facturas": sum(bool(item.impacta_fiscal) for item in facturas),
            "movimientos_stock": None, "costos_creados": None,
            "obligaciones_creadas": None, "eventos_fiscales": None,
            "conexiones_externas": None,
        },
        "detalle": {
            "ordenes": [{"id": item.id, "numero": getattr(item, "numero", None),
                "estado": getattr(item, "estado", None), "proveedor_id": getattr(item, "proveedor_id", None),
                "total_centavos": int(item.total_centavos),
                "items": [{"id": linea.id, "insumo_id": linea.insumo_id,
                    "descripcion": getattr(linea, "descripcion", None), "cantidad": str(linea.cantidad),
                    "unidad_medida": getattr(linea, "unidad_medida", None),
                    "precio_unitario_centavos": int(linea.precio_unitario_centavos),
                    "subtotal_centavos": int(linea.subtotal_centavos)} for linea in item.items]} for item in ordenes],
            "recepciones": [{"id": item.id, "numero": getattr(item, "numero", None),
                "orden_id": getattr(item, "orden_compra_id", None), "estado": item.estado,
                "subtotal_centavos": int(item.subtotal_centavos),
                "comprobante_referencia": getattr(item, "comprobante_referencia", None),
                "items": [{"orden_item_id": linea.orden_compra_item_id,
                    "cantidad_recibida": str(linea.cantidad_recibida)} for linea in item.items]} for item in recepciones],
            "facturas": [{"id": item.id, "recepcion_id": getattr(item, "recepcion_compra_id", None),
                "proveedor_id": item.proveedor_id, "tipo": item.tipo_comprobante,
                "punto_venta": item.punto_venta, "numero": item.numero, "estado": item.estado,
                "total_centavos": getattr(item, "total_centavos", None),
                "diferencia_centavos": int(item.diferencia_centavos)} for item in facturas],
            "propuestas": [{"id": item.id, "recepcion_id": getattr(item, "recepcion_compra_id", None),
                "tipo": item.tipo, "estado": item.estado, "ejecutada": bool(item.ejecutada),
                "motivo_decision": getattr(item, "motivo_decision", None),
                "decidido_por_usuario_id": getattr(item, "decidido_por_usuario_id", None),
                "fecha_decision": str(item.fecha_decision) if getattr(item, "fecha_decision", None) else None} for item in propuestas],
        },
    }
    resultado["huella_control"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_control(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
