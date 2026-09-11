"""Legajo integral offline para rendicion y auditoria de Mercado Pago."""

import csv
import hashlib
import io
import json
import zipfile

from services.conciliacion_liquidaciones_canal import construir_conciliaciones, incorporar_gestiones
from services.control_periodico_mp import construir_control_periodico


def _propios(registros, organizacion_id, unidad_negocio_id):
    return [
        registro for registro in (registros or [])
        if registro.organizacion_id == organizacion_id
        and registro.unidad_negocio_id == unidad_negocio_id
    ]


def _importe_firmado(movimiento):
    signo = 1 if movimiento.direccion == "credito" else -1
    return int(movimiento.importe_centavos) * signo


def construir_legajo_rendicion(ventas, movimientos, gestiones, cierres, *, organizacion_id, unidad_negocio_id):
    """Consolida evidencia local del tenant sin escribir ni consultar proveedores."""
    ventas = _propios(ventas, organizacion_id, unidad_negocio_id)
    movimientos = _propios(movimientos, organizacion_id, unidad_negocio_id)
    gestiones = _propios(gestiones, organizacion_id, unidad_negocio_id)
    cierres = _propios(cierres, organizacion_id, unidad_negocio_id)
    conciliaciones, resumen_estados = construir_conciliaciones(ventas, movimientos)
    incorporar_gestiones(conciliaciones, gestiones)
    tipos = {}
    for movimiento in movimientos:
        tipos[movimiento.tipo] = tipos.get(movimiento.tipo, 0) + _importe_firmado(movimiento)
    esperado = sum(int(venta.liquidacion_esperada_centavos) for venta in ventas if venta.estado not in {"cancelada", "devuelta"})
    real = sum(_importe_firmado(movimiento) for movimiento in movimientos if movimiento.impacta_saldo and movimiento.estado != "anulado")
    casos = [{
        "cuenta": fila["cuenta_codigo"],
        "venta": fila["referencia_venta"],
        "conciliacion": fila["estado_conciliacion"],
        "economico": fila["estado_economico"],
        "gestion": fila["estado_gestion"],
        "esperado_centavos": fila["liquidacion_esperada_centavos"],
        "real_centavos": fila["liquidacion_real_centavos"],
        "diferencia_centavos": fila["diferencia_centavos"],
        "requiere_revision": fila["requiere_revision"],
    } for fila in conciliaciones]
    control = construir_control_periodico(cierres, organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id)
    pendientes = sum(caso["requiere_revision"] and caso["gestion"] not in {"resuelta", "descartada"} for caso in casos)
    bloqueos = []
    if pendientes:
        bloqueos.append(f"Hay {pendientes} casos pendientes de resolucion interna.")
    if control["resumen"]["abiertos"]:
        bloqueos.append(f"Hay {control['resumen']['abiertos']} cierres todavia abiertos.")
    if not cierres:
        bloqueos.append("No existe un cierre auditable para el periodo.")
    return {
        "tenant": {"organizacion_id": organizacion_id, "unidad_negocio_id": unidad_negocio_id},
        "resumen": {
            "ventas": len(ventas), "movimientos": len(movimientos), "gestiones": len(gestiones),
            "cierres": len(cierres), "casos_pendientes": pendientes,
            "liquidacion_esperada_centavos": esperado, "liquidacion_real_centavos": real,
            "diferencia_centavos": real - esperado, "acciones_externas": 0,
        },
        "estados": resumen_estados,
        "movimientos_por_tipo_centavos": dict(sorted(tipos.items())),
        "casos": casos,
        "control_periodico": control,
        "bloqueos": bloqueos,
        "lista_para_archivar": not bloqueos,
        "puede_ejecutar": False,
    }


def _csv_bytes(encabezados, filas):
    salida = io.StringIO(newline="")
    escritor = csv.DictWriter(salida, fieldnames=encabezados)
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({campo: fila.get(campo) for campo in encabezados})
    return salida.getvalue().encode("utf-8-sig")


def exportar_legajo_zip(legajo):
    """Genera un ZIP autocontenido con manifiesto y huellas de integridad."""
    resumen = _csv_bytes(tuple(legajo["resumen"]), [legajo["resumen"]])
    campos_casos = ("cuenta", "venta", "conciliacion", "economico", "gestion", "esperado_centavos", "real_centavos", "diferencia_centavos", "requiere_revision")
    casos = _csv_bytes(campos_casos, legajo["casos"])
    periodos = _csv_bytes(("id", "fecha", "estado", "certificada", "ventas", "movimientos", "esperado_centavos", "real_centavos", "diferencia_centavos", "variacion_centavos", "requiere_revision", "puede_ejecutar"), legajo["control_periodico"]["filas"])
    evidencia = json.dumps(legajo, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8")
    archivos = {"resumen.csv": resumen, "casos.csv": casos, "periodos.csv": periodos, "evidencia.json": evidencia}
    manifiesto = {
        "formato": "legajo-rendicion-mp-v1", "acciones_externas": 0,
        "archivos": {nombre: hashlib.sha256(contenido).hexdigest() for nombre, contenido in archivos.items()},
    }
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as paquete:
        for nombre, contenido in archivos.items():
            paquete.writestr(nombre, contenido)
        paquete.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
        paquete.writestr("LEEME.txt", "Legajo local de rendicion Mercado Pago. No ejecuta cobros, devoluciones ni transferencias.\n".encode("utf-8"))
    salida.seek(0)
    return salida
