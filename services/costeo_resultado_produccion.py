"""Costeo realista del resultado productivo, sin modificar costos vigentes."""

import hashlib
import io
import json
from decimal import Decimal, ROUND_HALF_UP

from services.avances_produccion import resumir_orden


def _centavos(valor):
    return int(Decimal(str(valor)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cantidad(valor):
    return format(Decimal(str(valor)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP).normalize(), "f")


def costear_resultado(orden, *, organizacion_id, unidad_negocio_id):
    if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La orden no pertenece al tenant y unidad activos.")
    avance = resumir_orden(orden)
    buenas = Decimal(str(avance["buenas"]))
    rechazadas = Decimal(str(avance["rechazadas"]))
    informadas = buenas + rechazadas
    if informadas <= 0:
        raise ValueError("La orden no tiene producción informada para costear.")
    plan = Decimal(str(orden.cantidad_planificada))
    costo_plan = Decimal(int(orden.costo_planificado_centavos))
    costo_absorbido = costo_plan * informadas / plan
    costo_rechazo = costo_absorbido * rechazadas / informadas
    costo_buenas = costo_absorbido
    costo_unitario_efectivo = costo_buenas / buenas if buenas > 0 else None
    costo_unitario_plan = Decimal(int(orden.costo_unitario_centavos))
    desvio_unitario = None if costo_unitario_efectivo is None else costo_unitario_efectivo - costo_unitario_plan
    hallazgos = []
    if buenas <= 0:
        hallazgos.append({"codigo": "sin_unidades_buenas", "orden_id": orden.id})
    lotes = []
    total_lotes = Decimal("0")
    for lote in sorted(getattr(orden, "lotes_preparatorios", ()), key=lambda item: int(item.id)):
        if int(lote.organizacion_id) != int(organizacion_id) or int(lote.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "lote_fuera_contexto", "lote_id": lote.id})
            continue
        cantidad = Decimal(str(lote.cantidad)); total_lotes += cantidad
        costo_lote = None if costo_unitario_efectivo is None else costo_unitario_efectivo * cantidad
        lotes.append({
            "lote_id": lote.id, "codigo": lote.codigo, "estado_calidad": lote.estado,
            "cantidad": _cantidad(cantidad),
            "costo_teorico_centavos": None if costo_lote is None else _centavos(costo_lote),
            "costo_modificado": False,
        })
    if total_lotes > buenas:
        hallazgos.append({"codigo": "lotes_superan_produccion_buena", "orden_id": orden.id})
    resultado = {
        "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "orden_id": orden.id, "numero": orden.numero, "modo": "costeo_solo_lectura",
        "aprobado": not hallazgos,
        "cantidades": {"planificadas": _cantidad(plan), "buenas": _cantidad(buenas),
                       "rechazadas": _cantidad(rechazadas), "loteadas": _cantidad(total_lotes)},
        "costos": {
            "planificado_total_centavos": int(costo_plan),
            "planificado_unitario_centavos": int(costo_unitario_plan),
            "absorbido_avance_centavos": _centavos(costo_absorbido),
            "rechazo_absorbido_centavos": _centavos(costo_rechazo),
            "unitario_efectivo_centavos": None if costo_unitario_efectivo is None else _centavos(costo_unitario_efectivo),
            "desvio_unitario_centavos": None if desvio_unitario is None else _centavos(desvio_unitario),
        },
        "lotes": lotes, "hallazgos": hallazgos,
        "controles": {"persistencia": False, "versiones_costo_creadas": 0, "precios_modificados": 0,
                      "stock_modificado": False, "asientos_creados": 0, "conexiones_externas": 0},
    }
    resultado["huella_costeo"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_costeo(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
