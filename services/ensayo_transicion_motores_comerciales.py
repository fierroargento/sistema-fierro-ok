"""Ensaya en memoria la traducción del motor histórico al motor de canal."""

import hashlib
import io
import json
from decimal import Decimal, ROUND_HALF_UP

from services.motor_comercial_canal import liquidar_precio


def _comision(precio, porcentaje):
    return int(
        (Decimal(precio) * Decimal(str(porcentaje)) / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )
    )


def _candidato(politica):
    flete = int(politica.flete_venta_centavos)
    return {
        "origen_politica_id": int(politica.id),
        "comision_pct": str(politica.comision_pct),
        "publicidad_pct": "0",
        "financiacion_pct": "0",
        "devoluciones_pct": "0",
        "umbral_envio_centavos": 1 if flete else 0,
        "costo_envio_default_centavos": flete,
        "incremento_redondeo_centavos": int(politica.incremento_redondeo_centavos),
        "tramos": [{
            "precio_desde_centavos": 0,
            "precio_hasta_centavos": None,
            "cargo_fijo_centavos": int(politica.cargo_fijo_centavos),
        }],
        "margen_objetivo_pct_pendiente_regla_economica": str(politica.margen_objetivo_pct),
        "persistible": False,
    }


def _comparar_precio(item, politica, candidato):
    precio = int(item.precio_final_centavos)
    legado = precio - _comision(precio, politica.comision_pct)
    legado -= int(politica.cargo_fijo_centavos) + int(politica.flete_venta_centavos)
    tramo = type("Tramo", (), candidato["tramos"][0])()
    nuevo = liquidar_precio(
        precio,
        comision_pct=candidato["comision_pct"],
        tramos=[tramo],
        umbral_envio_centavos=candidato["umbral_envio_centavos"],
        costo_envio_centavos=candidato["costo_envio_default_centavos"],
    )["liquidacion_centavos"]
    return {
        "precio_item_id": int(item.id),
        "precio_final_centavos": precio,
        "vigente": bool(item.vigente),
        "liquidacion_legacy_centavos": legado,
        "liquidacion_candidata_centavos": nuevo,
        "diferencia_centavos": nuevo - legado,
        "equivalente": nuevo == legado,
    }


def construir_ensayo_transicion(listas, politicas, reglas_canal, items):
    resultados = []
    for lista in listas:
        legacy = [p for p in politicas if p.lista_precio_id == lista.id and p.vigente]
        nuevas = [r for r in reglas_canal if r.lista_precio_id == lista.id and r.vigente]
        precios = [item for item in items if item.lista_precio_id == lista.id]
        if len(legacy) != 1:
            resultados.append({
                "lista_id": int(lista.id), "lista": lista.nombre,
                "estado": "bloqueado", "motivo": "politica_historica_no_univoca",
                "candidato": None, "comparaciones": [], "aplicable": False,
            })
            continue
        candidato = _candidato(legacy[0])
        comparaciones = [_comparar_precio(item, legacy[0], candidato) for item in precios]
        equivalentes = all(item["equivalente"] for item in comparaciones)
        resultados.append({
            "lista_id": int(lista.id), "lista": lista.nombre,
            "estado": "equivalente" if equivalentes else "observado",
            "motivo": None if equivalentes else "diferencia_de_liquidacion",
            "candidato": candidato,
            "reglas_nuevas_vigentes": len(nuevas),
            "comparaciones": comparaciones,
            "precios_comparados": len(comparaciones),
            "aplicable": False,
        })
    resumen = {
        "listas": len(resultados),
        "equivalentes": sum(item["estado"] == "equivalente" for item in resultados),
        "observadas": sum(item["estado"] == "observado" for item in resultados),
        "bloqueadas": sum(item["estado"] == "bloqueado" for item in resultados),
        "precios_comparados": sum(item.get("precios_comparados", 0) for item in resultados),
    }
    base = {
        "tipo": "ensayo_transicion_motores_comerciales",
        "resumen": resumen,
        "resultados": resultados,
        "escrituras": 0,
        "reglas_creadas": 0,
        "precios_publicados": 0,
        "acciones_externas": 0,
    }
    firma = hashlib.sha256(
        json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**base, "firma_ensayo": firma}


def exportar_ensayo_transicion(ensayo):
    salida = io.BytesIO(json.dumps(ensayo, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
    salida.seek(0)
    return salida
