"""Plan agregado de materiales de produccion, local y no ejecutable."""

import hashlib
import io
import json
from decimal import Decimal, ROUND_HALF_UP

from services.avances_produccion import resumir_orden


SEIS = Decimal("0.000001")


def _numero(valor):
    return format(Decimal(str(valor)).quantize(SEIS, rounding=ROUND_HALF_UP).normalize(), "f")


def planificar_materiales(*, organizacion_id, unidad_negocio_id, ordenes, mapeos_insumo):
    """Asigna disponibilidad virtualmente y expone faltantes sin persistencia."""
    hallazgos = []
    candidatos = {}
    for mapeo in mapeos_insumo:
        if int(mapeo.organizacion_id) != int(organizacion_id) or int(mapeo.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "mapeo_fuera_contexto", "mapeo_id": mapeo.id})
            continue
        if not mapeo.activo:
            continue
        existencia = mapeo.existencia
        if int(existencia.organizacion_id) != int(organizacion_id):
            hallazgos.append({"codigo": "existencia_otro_tenant", "mapeo_id": mapeo.id})
            continue
        candidatos.setdefault(int(mapeo.insumo_id), []).append(mapeo)

    disponibilidad = {}
    asignaciones = []
    faltantes = {}
    ordenes_validas = []
    for orden in sorted(ordenes, key=lambda item: (int(item.id), str(item.numero))):
        if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "orden_fuera_contexto", "orden_id": orden.id})
            continue
        if orden.estado not in ("en_revision", "aprobada"):
            continue
        avance = resumir_orden(orden)
        pendiente = max(Decimal("0"), Decimal(str(avance["pendientes"])))
        proporcion = pendiente / Decimal(str(orden.cantidad_planificada))
        ordenes_validas.append(orden.id)
        for item in orden.insumos_planificados:
            mapeos = candidatos.get(int(item.insumo_id), [])
            if len(mapeos) != 1:
                hallazgos.append({
                    "codigo": "mapeo_faltante" if not mapeos else "mapeo_ambiguo",
                    "orden_id": orden.id, "insumo_id": item.insumo_id, "candidatos": len(mapeos),
                })
                continue
            existencia = mapeos[0].existencia
            clave = int(existencia.id)
            if clave not in disponibilidad:
                neta = max(
                    Decimal("0"),
                    Decimal(str(existencia.stock_actual))
                    - Decimal(str(existencia.stock_reservado))
                    - Decimal(str(existencia.stock_bloqueado)),
                )
                disponibilidad[clave] = neta
            requerida = (Decimal(str(item.cantidad_planificada)) * proporcion).quantize(SEIS, rounding=ROUND_HALF_UP)
            asignada = min(requerida, disponibilidad[clave])
            falta = requerida - asignada
            disponibilidad[clave] -= asignada
            asignaciones.append({
                "orden_id": orden.id, "numero": orden.numero, "insumo_id": item.insumo_id,
                "existencia_sucursal_id": clave, "requerida": _numero(requerida),
                "asignada_virtual": _numero(asignada), "faltante": _numero(falta),
                "reserva_creada": False,
            })
            if falta > 0:
                dato = faltantes.setdefault((int(item.insumo_id), clave), {
                    "insumo_id": item.insumo_id, "existencia_sucursal_id": clave,
                    "cantidad": Decimal("0"), "ordenes": [],
                })
                dato["cantidad"] += falta
                dato["ordenes"].append(orden.id)

    sugerencias = []
    for (insumo_id, existencia_id), dato in sorted(faltantes.items()):
        cantidad = _numero(dato["cantidad"])
        sugerencias.append({
            "tipo": "compra_sugerida", "insumo_id": insumo_id,
            "existencia_sucursal_id": existencia_id, "cantidad": cantidad,
            "ordenes_origen": dato["ordenes"],
            "clave_idempotencia": f"mrp:{organizacion_id}:{unidad_negocio_id}:{insumo_id}:{existencia_id}:{cantidad}",
            "orden_compra_creada": False,
        })

    resultado = {
        "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "modo": "planificacion_no_ejecutable", "aprobado": not hallazgos,
        "resumen": {
            "ordenes_consideradas": len(ordenes_validas), "asignaciones": len(asignaciones),
            "insumos_con_faltante": len(sugerencias),
        },
        "asignaciones_virtuales": asignaciones, "sugerencias_compra": sugerencias,
        "hallazgos": hallazgos,
        "controles": {
            "persistencia": False, "reservas_creadas": 0, "movimientos_creados": 0,
            "ordenes_compra_creadas": 0, "stock_modificado": False, "conexiones_externas": 0,
        },
    }
    resultado["huella_plan"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_plan(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
