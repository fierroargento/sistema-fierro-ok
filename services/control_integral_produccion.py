"""Control integral firmado del circuito productivo preparatorio."""

import hashlib
import io
import json
from decimal import Decimal

from services.avances_produccion import resumir_orden
from services.simulacion_cierre_produccion import simular_cierre


def controlar_produccion(*, organizacion_id, unidad_negocio_id, ordenes):
    hallazgos = []
    simulaciones = []
    for orden in ordenes:
        if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "orden_fuera_contexto", "orden_id": orden.id})
            continue
        if orden.impacta_inventario or orden.ejecucion_habilitada:
            hallazgos.append({"codigo": "orden_ejecutable", "orden_id": orden.id})
        if not orden.insumos_planificados or not orden.operaciones_planificadas:
            hallazgos.append({"codigo": "plan_incompleto", "orden_id": orden.id})
        esperado = int(
            (Decimal(str(orden.cantidad_planificada)) * Decimal(int(orden.costo_unitario_centavos))).quantize(Decimal("1"))
        )
        if esperado != int(orden.costo_planificado_centavos):
            hallazgos.append({"codigo": "costo_plan_inconsistente", "orden_id": orden.id})
        avance = resumir_orden(orden)
        if avance["pendientes"] < 0:
            hallazgos.append({"codigo": "sobreproduccion", "orden_id": orden.id})
        for parte in orden.partes_informados:
            if parte.impacta_inventario or parte.consume_insumos or parte.crea_producto_terminado:
                hallazgos.append({"codigo": "parte_con_impacto", "parte_id": parte.id})
        if orden.estado == "aprobada" and avance["informadas"] > 0:
            simulacion = simular_cierre(
                orden, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
            )
            simulaciones.append({
                "orden_id": orden.id,
                "huella_simulacion": simulacion["huella_simulacion"],
                "completa": simulacion["completa"],
            })
    resultado = {
        "organizacion_id": organizacion_id,
        "unidad_negocio_id": unidad_negocio_id,
        "modo": "solo_lectura",
        "aprobado": not hallazgos,
        "resumen": {
            "ordenes": len(ordenes),
            "aprobadas": sum(item.estado == "aprobada" for item in ordenes),
            "partes": sum(len(item.partes_informados) for item in ordenes),
            "simulaciones": len(simulaciones),
            "hallazgos": len(hallazgos),
        },
        "hallazgos": hallazgos,
        "simulaciones": simulaciones,
        "controles": {
            "persistencia": False, "consumos": 0, "movimientos_stock": 0,
            "productos_terminados_creados": 0, "costos_modificados": 0,
            "conexiones_externas": 0,
        },
    }
    resultado["huella_control"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_control(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
