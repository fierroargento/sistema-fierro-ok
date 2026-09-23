"""Propuestas firmadas de inventario para Produccion, siempre no ejecutables."""

import hashlib
import io
import json
from decimal import Decimal

from services.simulacion_cierre_produccion import simular_cierre


def _decimal(valor):
    return format(Decimal(str(valor)).normalize(), "f")


def preparar_propuesta_inventario(
    orden, *, organizacion_id, unidad_negocio_id, mapeos_insumo, existencias_producto,
):
    """Compone consumos e ingreso teóricos sin escribir ni ejecutar movimientos."""
    simulacion = simular_cierre(
        orden, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    )
    hallazgos = []
    mapeos_activos = {}
    for mapeo in mapeos_insumo:
        if int(mapeo.organizacion_id) != int(organizacion_id) or int(mapeo.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "mapeo_insumo_fuera_contexto", "mapeo_id": mapeo.id})
            continue
        if not mapeo.activo:
            continue
        insumo = mapeo.insumo
        if int(insumo.organizacion_id) != int(organizacion_id):
            hallazgos.append({"codigo": "insumo_mapeado_otro_tenant", "mapeo_id": mapeo.id})
            continue
        if insumo.unidad_negocio_id not in {None, unidad_negocio_id}:
            hallazgos.append({"codigo": "insumo_mapeado_otra_unidad", "mapeo_id": mapeo.id})
            continue
        if not insumo.activo:
            hallazgos.append({"codigo": "insumo_mapeado_inactivo", "mapeo_id": mapeo.id})
            continue
        existencia = mapeo.existencia
        if int(existencia.organizacion_id) != int(organizacion_id):
            hallazgos.append({"codigo": "existencia_insumo_otro_tenant", "mapeo_id": mapeo.id})
            continue
        if not existencia.control_activo:
            hallazgos.append({"codigo": "existencia_insumo_sin_control", "mapeo_id": mapeo.id})
            continue
        mapeos_activos.setdefault(int(mapeo.insumo_id), []).append(mapeo)

    consumos = []
    for consumo in simulacion["consumos_teoricos"]:
        candidatos = mapeos_activos.get(int(consumo["insumo_id"]), [])
        if len(candidatos) != 1:
            hallazgos.append({
                "codigo": "mapeo_insumo_faltante" if not candidatos else "mapeo_insumo_ambiguo",
                "insumo_id": consumo["insumo_id"], "candidatos": len(candidatos),
            })
            continue
        existencia = candidatos[0].existencia
        cantidad = consumo["cantidad_teorica"]
        consumos.append({
            "tipo": "salida_teorica", "insumo_id": consumo["insumo_id"],
            "existencia_sucursal_id": existencia.id, "cantidad": cantidad,
            "clave_idempotencia": f"produccion:{orden.id}:consumo:{consumo['insumo_id']}:{cantidad}",
            "ejecutado": False,
        })

    destinos = [
        existencia for existencia in existencias_producto
        if int(existencia.organizacion_id) == int(organizacion_id)
        and int(existencia.producto_id) == int(orden.producto_id)
        and bool(existencia.control_activo)
    ]
    ajenos = [
        existencia for existencia in existencias_producto
        if int(existencia.organizacion_id) != int(organizacion_id)
    ]
    if ajenos:
        hallazgos.append({"codigo": "destino_producto_otro_tenant", "cantidad": len(ajenos)})
    ingreso = None
    if len(destinos) != 1:
        hallazgos.append({
            "codigo": "destino_producto_faltante" if not destinos else "destino_producto_ambiguo",
            "producto_id": orden.producto_id, "candidatos": len(destinos),
        })
    else:
        cantidad = simulacion["propuestas"]["ingreso_producto_terminado"]
        ingreso = {
            "tipo": "entrada_teorica", "producto_id": orden.producto_id,
            "existencia_sucursal_id": destinos[0].id, "cantidad": cantidad,
            "clave_idempotencia": f"produccion:{orden.id}:producto:{orden.producto_id}:{cantidad}",
            "ejecutado": False,
        }

    movimientos = consumos + ([ingreso] if ingreso else [])
    reversion = [
        {
            **movimiento,
            "tipo": "entrada_teorica" if movimiento["tipo"] == "salida_teorica" else "salida_teorica",
            "clave_idempotencia": f"reversion:{movimiento['clave_idempotencia']}",
        }
        for movimiento in reversed(movimientos)
    ]
    resultado = {
        "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "orden_id": orden.id, "numero": orden.numero,
        "modo": "propuesta_no_ejecutable", "aprobada": not hallazgos,
        "huella_simulacion": simulacion["huella_simulacion"],
        "movimientos_propuestos": movimientos, "reversion_teorica": reversion,
        "hallazgos": hallazgos,
        "controles": {
            "persistencia": False, "movimientos_creados": 0, "stock_modificado": False,
            "orden_cerrada": False, "costos_modificados": False, "conexiones_externas": 0,
        },
    }
    resultado["huella_propuesta"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_propuesta(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
