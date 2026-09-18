"""Compara el motor histórico de listas con el motor vigente, sin migrar datos."""

import hashlib
import io
import json
from decimal import Decimal


def _vigentes(registros, lista_id):
    return [item for item in registros if item.lista_precio_id == lista_id and item.vigente]


def _cargo_inicial(regla):
    tramos = [item for item in getattr(regla, "tramos", ()) if int(item.precio_desde_centavos) == 0]
    return int(tramos[0].cargo_fijo_centavos) if len(tramos) == 1 else None


def construir_control_motores(listas, politicas_legacy, reglas_canal, items):
    filas = []
    for lista in listas:
        legacy = _vigentes(politicas_legacy, lista.id)
        nuevas = _vigentes(reglas_canal, lista.id)
        bloqueos, diferencias, avisos = [], [], []
        if len(legacy) > 1:
            bloqueos.append("multiples_politicas_historicas_vigentes")
        if len(nuevas) > 1:
            bloqueos.append("multiples_reglas_canal_vigentes")
        politica = legacy[0] if len(legacy) == 1 else None
        regla = nuevas[0] if len(nuevas) == 1 else None
        if len(legacy) <= 1 and len(nuevas) <= 1:
            if politica and not regla:
                bloqueos.append("solo_motor_historico")
            elif regla and not politica:
                avisos.append("lista_ya_depende_solo_del_motor_nuevo")
            elif not politica and not regla:
                bloqueos.append("lista_sin_politica_vigente")
        if politica and regla:
            if Decimal(str(politica.comision_pct)) != Decimal(str(regla.comision_pct)):
                diferencias.append("comision_distinta")
            if int(politica.incremento_redondeo_centavos) != int(regla.incremento_redondeo_centavos):
                diferencias.append("redondeo_distinto")
            if int(politica.flete_venta_centavos) != int(regla.costo_envio_default_centavos):
                diferencias.append("flete_envio_distinto")
            cargo = _cargo_inicial(regla)
            if cargo is None:
                diferencias.append("cargo_historico_sin_tramo_equivalente")
            elif int(politica.cargo_fijo_centavos) != cargo:
                diferencias.append("cargo_fijo_distinto")
            avisos.append("margen_historico_debe_resolverse_con_regla_economica")
        precios = [item for item in items if item.lista_precio_id == lista.id]
        estado = "bloqueada" if bloqueos else "divergente" if diferencias else "alineada"
        filas.append({
            "lista_id": int(lista.id), "lista": lista.nombre,
            "estado": estado, "bloqueos": bloqueos,
            "diferencias": diferencias, "avisos": avisos,
            "politica_legacy_id": getattr(politica, "id", None),
            "regla_canal_id": getattr(regla, "id", None),
            "precios_historicos": len(precios),
            "precios_vigentes": sum(bool(item.vigente) for item in precios),
            "retiro_legacy_habilitado": bool(politica and regla and not bloqueos and not diferencias),
        })
    resumen = {
        "listas": len(filas),
        "alineadas": sum(item["estado"] == "alineada" for item in filas),
        "divergentes": sum(item["estado"] == "divergente" for item in filas),
        "bloqueadas": sum(item["estado"] == "bloqueada" for item in filas),
        "retiro_legacy_habilitado": sum(item["retiro_legacy_habilitado"] for item in filas),
    }
    base = {"filas": filas, "resumen": resumen}
    firma = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return {**base, "firma_evidencia": firma, "escrituras": 0, "migraciones": 0, "acciones_externas": 0}


def exportar_control_motores(resultado):
    salida = io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
    salida.seek(0)
    return salida
