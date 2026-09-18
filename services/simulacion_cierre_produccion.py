"""Simula el cierre productivo en memoria, sin ejecutar sus efectos."""

import hashlib
import io
import json
from decimal import Decimal, ROUND_HALF_UP

from services.avances_produccion import resumir_orden


def _texto_decimal(valor):
    return format(Decimal(str(valor)).normalize(), "f")


def simular_cierre(orden, *, organizacion_id, unidad_negocio_id):
    if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La orden no pertenece al tenant y unidad activos.")
    if orden.estado != "aprobada":
        raise ValueError("Solo una orden aprobada admite simulación de cierre.")
    avance = resumir_orden(orden)
    plan = Decimal(str(orden.cantidad_planificada))
    informadas = avance["informadas"]
    if informadas <= 0:
        raise ValueError("La orden todavía no tiene avances informados.")
    proporcion = informadas / plan
    consumos = []
    for item in orden.insumos_planificados:
        teorico = (Decimal(str(item.cantidad_planificada)) * proporcion).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP,
        )
        consumos.append({
            "insumo_id": item.insumo_id,
            "cantidad_teorica": _texto_decimal(teorico),
            "movimiento_creado": False,
        })
    minutos_planificados = sum(
        Decimal(str(item.minutos_planificados)) * proporcion
        for item in orden.operaciones_planificadas
    )
    costo_informado = int(
        (Decimal(int(orden.costo_planificado_centavos)) * proporcion).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )
    )
    resultado = {
        "organizacion_id": organizacion_id,
        "unidad_negocio_id": unidad_negocio_id,
        "orden_id": orden.id,
        "numero": orden.numero,
        "modo": "simulacion_no_ejecutable",
        "completa": avance["pendientes"] == 0,
        "avance": {
            "buenas": _texto_decimal(avance["buenas"]),
            "rechazadas": _texto_decimal(avance["rechazadas"]),
            "pendientes": _texto_decimal(avance["pendientes"]),
        },
        "consumos_teoricos": consumos,
        "tiempos": {
            "planificados_proporcionales": _texto_decimal(minutos_planificados),
            "reales_informados": _texto_decimal(avance["minutos_reales"]),
            "desvio_minutos": _texto_decimal(avance["minutos_reales"] - minutos_planificados),
        },
        "costos": {
            "planificado_proporcional_centavos": costo_informado,
            "costo_modificado": False,
        },
        "propuestas": {
            "ingreso_producto_terminado": _texto_decimal(avance["buenas"]),
            "merma_rechazo": _texto_decimal(avance["rechazadas"]),
            "movimientos_creados": 0,
            "ejecutable": False,
        },
        "controles": {
            "persistencia": False, "consumos_reales": 0,
            "altas_stock": 0, "cambios_costos": 0,
            "conexiones_externas": 0,
        },
    }
    resultado["huella_simulacion"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_simulacion(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
