"""Genera un plan offline para retirar gradualmente el motor comercial histórico."""

import hashlib
import io
import json


ACCIONES_DIFERENCIA = {
    "comision_distinta": "alinear_comision",
    "redondeo_distinto": "alinear_redondeo",
    "flete_envio_distinto": "alinear_costo_envio",
    "cargo_fijo_distinto": "alinear_cargo_fijo",
    "cargo_historico_sin_tramo_equivalente": "crear_tramo_equivalente",
}

ACCIONES_BLOQUEO = {
    "multiples_politicas_historicas_vigentes": "resolver_duplicados_historicos",
    "multiples_reglas_canal_vigentes": "resolver_duplicados_nuevos",
    "solo_motor_historico": "crear_regla_canal_equivalente",
    "lista_sin_politica_vigente": "definir_politica_comercial",
}


def _accion(clave, orden, obligatoria=True):
    return {
        "orden": orden,
        "clave": clave,
        "obligatoria": obligatoria,
        "estado": "pendiente",
        "ejecucion_automatica": False,
    }


def construir_plan_transicion(control):
    listas = []
    for fila in control["filas"]:
        acciones = []
        for bloqueo in fila["bloqueos"]:
            acciones.append(_accion(ACCIONES_BLOQUEO[bloqueo], len(acciones) + 1))
        for diferencia in fila["diferencias"]:
            acciones.append(_accion(ACCIONES_DIFERENCIA[diferencia], len(acciones) + 1))
        if "margen_historico_debe_resolverse_con_regla_economica" in fila["avisos"]:
            acciones.append(_accion("validar_regla_economica", len(acciones) + 1))
        if fila["precios_vigentes"]:
            acciones.append(_accion("comparar_precios_en_sombra", len(acciones) + 1))
        preparado = bool(fila["retiro_legacy_habilitado"] and not acciones)
        if preparado:
            acciones.append(_accion("autorizar_retiro_en_cambio_futuro", 1))
        fase = (
            "resolver_bloqueos" if fila["bloqueos"] else
            "alinear_parametros" if fila["diferencias"] else
            "validar_resultados" if not preparado else
            "listo_para_decision"
        )
        listas.append({
            "lista_id": fila["lista_id"],
            "lista": fila["lista"],
            "fase": fase,
            "acciones": acciones,
            "cantidad_acciones": len(acciones),
            "retiro_automatico": False,
            "requiere_aprobacion_futura": True,
        })
    resumen = {
        "listas": len(listas),
        "resolver_bloqueos": sum(item["fase"] == "resolver_bloqueos" for item in listas),
        "alinear_parametros": sum(item["fase"] == "alinear_parametros" for item in listas),
        "validar_resultados": sum(item["fase"] == "validar_resultados" for item in listas),
        "listas_para_decision": sum(item["fase"] == "listo_para_decision" for item in listas),
        "acciones_pendientes": sum(item["cantidad_acciones"] for item in listas),
    }
    base = {
        "tipo": "plan_transicion_motores_comerciales",
        "firma_control_origen": control["firma_evidencia"],
        "resumen": resumen,
        "listas": listas,
        "garantias": {
            "solo_lectura": True,
            "sin_migraciones": True,
            "sin_publicacion_precios": True,
            "sin_conexiones_externas": True,
        },
    }
    firma = hashlib.sha256(
        json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**base, "firma_plan": firma}


def exportar_plan_transicion(plan):
    contenido = json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    salida = io.BytesIO(contenido)
    salida.seek(0)
    return salida
