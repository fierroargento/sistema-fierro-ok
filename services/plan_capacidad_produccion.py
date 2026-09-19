"""Carga agregada de personas y maquinas para produccion preparatoria."""

import hashlib
import io
import json
from decimal import Decimal, ROUND_HALF_UP

from services.avances_produccion import resumir_orden


CUATRO = Decimal("0.0001")


def _texto(valor):
    return format(Decimal(str(valor)).quantize(CUATRO, rounding=ROUND_HALF_UP).normalize(), "f")


def _capacidades(versiones, atributo_recurso, atributo_horas, organizacion_id, unidad_negocio_id, hallazgos):
    resultado = {}
    for version in versiones:
        recurso = getattr(version, atributo_recurso)
        if int(recurso.organizacion_id) != int(organizacion_id):
            hallazgos.append({"codigo": "recurso_fuera_tenant", "recurso_id": recurso.id})
            continue
        unidad = getattr(recurso, "unidad_negocio_id", None)
        if unidad is not None and int(unidad) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "recurso_fuera_unidad", "recurso_id": recurso.id})
            continue
        if not version.vigente or not recurso.activo:
            continue
        if recurso.id in resultado:
            hallazgos.append({"codigo": "capacidad_vigente_ambigua", "recurso_id": recurso.id})
            continue
        resultado[recurso.id] = {
            "recurso": recurso,
            "minutos": Decimal(str(getattr(version, atributo_horas))) * Decimal("60"),
        }
    return resultado


def planificar_capacidad(
    *, organizacion_id, unidad_negocio_id, ordenes, versiones_empleado, versiones_maquina,
):
    hallazgos = []
    personas = _capacidades(
        versiones_empleado, "empleado", "horas_productivas",
        organizacion_id, unidad_negocio_id, hallazgos,
    )
    maquinas = _capacidades(
        versiones_maquina, "maquina", "horas_productivas_mensuales",
        organizacion_id, unidad_negocio_id, hallazgos,
    )
    carga_persona = {}
    carga_maquina = {}
    secuencia = []
    activas = []
    for orden in sorted(ordenes, key=lambda item: (0 if item.estado == "aprobada" else 1, int(item.id))):
        if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
            hallazgos.append({"codigo": "orden_fuera_contexto", "orden_id": orden.id})
            continue
        if orden.estado not in ("aprobada", "en_revision"):
            continue
        avance = resumir_orden(orden)
        pendiente = max(Decimal("0"), Decimal(str(avance["pendientes"])))
        proporcion = pendiente / Decimal(str(orden.cantidad_planificada))
        activas.append(orden.id)
        minutos_persona = Decimal("0")
        minutos_maquina = Decimal("0")
        for operacion in orden.operaciones_planificadas:
            minutos = Decimal(str(operacion.minutos_planificados)) * proporcion
            carga_persona[operacion.empleado_id] = carga_persona.get(operacion.empleado_id, Decimal("0")) + minutos
            minutos_persona += minutos
            if operacion.empleado_id not in personas:
                hallazgos.append({"codigo": "capacidad_persona_faltante", "orden_id": orden.id,
                                  "empleado_id": operacion.empleado_id})
        for uso in orden.maquinas_planificadas:
            minutos = Decimal(str(uso.minutos_planificados)) * proporcion
            carga_maquina[uso.maquina_id] = carga_maquina.get(uso.maquina_id, Decimal("0")) + minutos
            minutos_maquina += minutos
            if uso.maquina_id not in maquinas:
                hallazgos.append({"codigo": "capacidad_maquina_faltante", "orden_id": orden.id,
                                  "maquina_id": uso.maquina_id})
        secuencia.append({
            "posicion": len(secuencia) + 1, "orden_id": orden.id, "numero": orden.numero,
            "estado": orden.estado, "cantidad_pendiente": _texto(pendiente),
            "minutos_persona": _texto(minutos_persona), "minutos_maquina": _texto(minutos_maquina),
            "inicio_programado": False,
        })

    def resumir(cargas, capacidades, tipo):
        filas = []
        for recurso_id in sorted(set(cargas) | set(capacidades)):
            carga = cargas.get(recurso_id, Decimal("0"))
            capacidad = capacidades.get(recurso_id, {}).get("minutos", Decimal("0"))
            sobrecarga = max(Decimal("0"), carga - capacidad)
            utilizacion = (carga * Decimal("100") / capacidad) if capacidad > 0 else None
            filas.append({
                "tipo": tipo, "recurso_id": recurso_id, "carga_minutos": _texto(carga),
                "capacidad_minutos": _texto(capacidad),
                "utilizacion_pct": None if utilizacion is None else _texto(utilizacion),
                "sobrecarga_minutos": _texto(sobrecarga), "calendario_modificado": False,
            })
        return filas

    carga_personas = resumir(carga_persona, personas, "persona")
    carga_maquinas = resumir(carga_maquina, maquinas, "maquina")
    cuellos = [x for x in carga_personas + carga_maquinas if Decimal(x["sobrecarga_minutos"]) > 0]
    resultado = {
        "organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id,
        "modo": "capacidad_no_ejecutable", "aprobado": not hallazgos and not cuellos,
        "resumen": {"ordenes": len(activas), "personas": len(carga_personas),
                    "maquinas": len(carga_maquinas), "cuellos_botella": len(cuellos)},
        "secuencia_sugerida": secuencia, "carga_personas": carga_personas,
        "carga_maquinas": carga_maquinas, "cuellos_botella": cuellos, "hallazgos": hallazgos,
        "controles": {"persistencia": False, "ordenes_iniciadas": 0, "calendarios_modificados": 0,
                      "partes_creados": 0, "stock_modificado": False, "conexiones_externas": 0},
    }
    resultado["huella_capacidad"] = hashlib.sha256(
        json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return resultado


def exportar_capacidad(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
