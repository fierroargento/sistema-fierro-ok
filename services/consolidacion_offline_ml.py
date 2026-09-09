"""Cruza snapshots ML con el control interno sin persistir ni ejecutar acciones."""

import hashlib
import json
from io import BytesIO


CONTRATO_EFECTOS = {
    "persistencia": False,
    "publicacion": False,
    "cancelacion_promocion": False,
    "cambio_precio": False,
    "pausa_publicacion": False,
}


def _sku_control(fila):
    return str(fila["costo"].producto.sku or "").strip().upper()


def _lista_control(fila):
    return int(fila["regla_canal"].lista_precio_id)


def _acciones(fila, observado):
    actual = int(observado["precio_centavos"])
    objetivo = int(fila["propuesto"]["precio_final_centavos"])
    requiere_precio = objetivo > actual or not observado["cumple_piso"]
    if not requiere_precio:
        return []
    acciones = []
    if observado["promocion_activa"]:
        acciones.append({
            "orden": 1, "accion": "cancelar_promocion_manual",
            "depende_de": None, "ejecutada": False,
        })
    acciones.append({
        "orden": len(acciones) + 1,
        "accion": "actualizar_precio_manual",
        "precio_objetivo_centavos": objetivo,
        "depende_de": "cancelar_promocion_manual" if acciones else None,
        "ejecutada": False,
    })
    return acciones


def consolidar_snapshot_ml(snapshot, filas_control, *, lista_precio_id):
    """Usa el snapshot como observacion y el sistema como fuente del piso."""
    lista_id = int(lista_precio_id)
    indices = {}
    for fila in filas_control or []:
        if _lista_control(fila) == lista_id:
            indices.setdefault(_sku_control(fila), []).append(fila)
    resultados = []
    for observado in snapshot.get("resultados") or []:
        sku = str(observado.get("sku") or "").strip().upper()
        candidatas = indices.get(sku, [])
        if len(candidatas) != 1:
            resultados.append({
                "publicacion": observado,
                "estado": "bloqueada",
                "bloqueos": [
                    "sku_sin_control_interno" if not candidatas
                    else "sku_con_control_interno_ambiguo"
                ],
                "desvios": [], "acciones": [],
            })
            continue
        fila = candidatas[0]
        regla = fila["regla_canal"]
        piso_minimo = int(fila["minimo"]["piso_liquidacion_centavos"])
        piso_objetivo = int(fila["objetivo"]["piso_liquidacion_centavos"])
        liquidacion = int(observado["liquidacion_centavos"])
        desvios = []
        if str(observado["comision_pct"]) != str(regla.comision_pct):
            desvios.append("comision_ml_distinta_de_politica")
        actual_interno = fila.get("actual")
        if actual_interno is not None:
            if int(observado["cargo_fijo_centavos"]) != int(actual_interno["cargo_fijo_centavos"]):
                desvios.append("cargo_fijo_ml_distinto_de_politica")
            if int(observado["envio_centavos"]) != int(actual_interno["envio_centavos"]):
                desvios.append("envio_ml_distinto_de_politica")
        estado = (
            "debajo_del_piso" if liquidacion < piso_minimo
            else "al_limite" if liquidacion < piso_objetivo
            else "rentable"
        )
        acciones = _acciones(fila, observado)
        resultados.append({
            "publicacion": observado,
            "estado": estado,
            "bloqueos": [],
            "desvios": desvios,
            "costo_version_id": getattr(fila["costo"], "id", None),
            "regla_economica_id": getattr(fila.get("regla"), "id", None),
            "regla_canal_id": getattr(regla, "id", None),
            "catalogo_producto_id": getattr(fila.get("inclusion"), "id", None),
            "piso_minimo_centavos": piso_minimo,
            "piso_objetivo_centavos": piso_objetivo,
            "precio_objetivo_centavos": int(fila["propuesto"]["precio_final_centavos"]),
            "margen_minimo_centavos": liquidacion - piso_minimo,
            "acciones": acciones,
        })
    resumen = {
        "publicaciones": len(resultados),
        "rentables": sum(item["estado"] == "rentable" for item in resultados),
        "al_limite": sum(item["estado"] == "al_limite" for item in resultados),
        "debajo_del_piso": sum(item["estado"] == "debajo_del_piso" for item in resultados),
        "bloqueadas": sum(item["estado"] == "bloqueada" for item in resultados),
        "con_desvios": sum(bool(item["desvios"]) for item in resultados),
        "acciones_preparadas": sum(len(item["acciones"]) for item in resultados),
    }
    base = {"lista_precio_id": lista_id, "resultados": resultados, "resumen": resumen}
    firma = hashlib.sha256(json.dumps(
        base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")).hexdigest()
    return {
        **base, "firma_evidencia": firma,
        "contrato_efectos": dict(CONTRATO_EFECTOS),
        "acciones_externas": 0, "escrituras": 0,
        "aplicable": False,
    }


def exportar_consolidacion_json(resultado):
    salida = BytesIO(json.dumps(
        resultado, ensure_ascii=False, sort_keys=True, indent=2, default=str,
    ).encode("utf-8"))
    salida.seek(0)
    return salida
