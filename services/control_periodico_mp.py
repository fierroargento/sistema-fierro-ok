"""Control periodico offline sobre cierres de conciliacion Mercado Pago."""

import csv
import io
import json


ESTADOS_ABIERTOS = {"preparado", "revision", "aprobado"}
ESTADOS_TERMINALES = {"cerrado", "archivado"}


def _snapshot(cierre):
    try:
        return json.loads(cierre.snapshot_json or "{}")
    except (TypeError, ValueError):
        return {}


def _total(snapshot, campo):
    return sum(int(fila.get(campo) or 0) for fila in snapshot.get("filas", []))


def construir_control_periodico(cierres, *, organizacion_id, unidad_negocio_id):
    """Resume y compara cierres ya registrados, sin consultar servicios externos."""
    propios = [
        cierre for cierre in (cierres or [])
        if cierre.organizacion_id == organizacion_id
        and cierre.unidad_negocio_id == unidad_negocio_id
    ]
    propios.sort(key=lambda cierre: (cierre.fecha_creacion, cierre.id), reverse=True)
    filas = []
    for indice, cierre in enumerate(propios):
        actual = _snapshot(cierre)
        anterior = _snapshot(propios[indice + 1]) if indice + 1 < len(propios) else {}
        esperado = _total(actual, "esperado")
        real = _total(actual, "real")
        diferencia = _total(actual, "diferencia")
        diferencia_anterior = _total(anterior, "diferencia") if anterior else None
        variacion = diferencia - diferencia_anterior if diferencia_anterior is not None else None
        certificacion = json.loads(cierre.certificacion_json or "{}")
        filas.append({
            "id": cierre.id,
            "fecha": cierre.fecha_creacion,
            "estado": cierre.estado,
            "certificada": bool(certificacion.get("aprobada")),
            "ventas": len(actual.get("ventas_ids", [])),
            "movimientos": len(actual.get("movimientos_ids", [])),
            "esperado_centavos": esperado,
            "real_centavos": real,
            "diferencia_centavos": diferencia,
            "variacion_centavos": variacion,
            "requiere_revision": cierre.estado in ESTADOS_ABIERTOS or diferencia != 0,
            "puede_ejecutar": False,
        })
    abiertos = sum(fila["estado"] in ESTADOS_ABIERTOS for fila in filas)
    descuadrados = sum(fila["diferencia_centavos"] != 0 for fila in filas)
    return {
        "filas": filas,
        "resumen": {
            "cierres": len(filas),
            "abiertos": abiertos,
            "cerrados": sum(fila["estado"] in ESTADOS_TERMINALES for fila in filas),
            "descuadrados": descuadrados,
            "bloqueados": sum(not fila["certificada"] for fila in filas),
            "acciones_externas": 0,
        },
    }


def exportar_control_periodico(reporte, formato="csv"):
    """Exporta evidencia en memoria; no persiste ni transmite informacion."""
    if formato == "json":
        contenido = json.dumps(reporte, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        return io.BytesIO(contenido), "application/json", "control_periodico_mp.json"
    salida = io.StringIO(newline="")
    campos = ("id", "fecha", "estado", "certificada", "ventas", "movimientos", "esperado_centavos", "real_centavos", "diferencia_centavos", "variacion_centavos", "requiere_revision", "puede_ejecutar")
    escritor = csv.DictWriter(salida, fieldnames=campos)
    escritor.writeheader()
    for fila in reporte.get("filas", []):
        escritor.writerow({campo: fila.get(campo) for campo in campos})
    return io.BytesIO(salida.getvalue().encode("utf-8-sig")), "text/csv", "control_periodico_mp.csv"
