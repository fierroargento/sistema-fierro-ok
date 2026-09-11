"""Certificacion integral offline de la preparacion Mercado Pago."""

import hashlib
import io
import json
import zipfile

from services.certificacion_offline_mercado_pago import certificar_conciliacion_mp
from services.control_periodico_mp import construir_control_periodico
from services.gestion_lotes_importacion_mp import diagnosticar_lote
from services.legajo_rendicion_mp import construir_legajo_rendicion


def _propios(registros, organizacion_id, unidad_negocio_id):
    return [
        registro for registro in (registros or [])
        if registro.organizacion_id == organizacion_id
        and registro.unidad_negocio_id == unidad_negocio_id
    ]


def _control(nombre, aprobado, detalle, *, cantidad=0):
    return {
        "nombre": nombre,
        "aprobado": bool(aprobado),
        "estado": "aprobado" if aprobado else "bloqueado",
        "detalle": detalle,
        "cantidad": int(cantidad or 0),
    }


def certificar_preparacion_mp(
    ventas, movimientos, gestiones, cierres, lotes, *,
    organizacion_id, unidad_negocio_id,
):
    """Cruza toda la evidencia local sin escribir ni consultar Mercado Pago."""
    ventas = _propios(ventas, organizacion_id, unidad_negocio_id)
    movimientos = _propios(movimientos, organizacion_id, unidad_negocio_id)
    gestiones = _propios(gestiones, organizacion_id, unidad_negocio_id)
    cierres = _propios(cierres, organizacion_id, unidad_negocio_id)
    lotes = _propios(lotes, organizacion_id, unidad_negocio_id)

    conciliacion = certificar_conciliacion_mp(
        ventas, movimientos, gestiones,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )
    control_periodico = construir_control_periodico(
        cierres,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )
    legajo = construir_legajo_rendicion(
        ventas, movimientos, gestiones, cierres,
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
    )

    diagnosticos_lotes = [
        diagnosticar_lote(
            lote, movimientos,
            organizacion_id=organizacion_id,
            unidad_negocio_id=unidad_negocio_id,
        )
        for lote in lotes
    ]
    lotes_inconsistentes = [
        diagnostico for diagnostico in diagnosticos_lotes
        if diagnostico["lote"].estado == "confirmado" and diagnostico["bloqueos"]
    ]
    huellas = [lote.huella_documento for lote in lotes]
    huellas_duplicadas = len(huellas) - len(set(huellas))
    cierres_terminales = [cierre for cierre in cierres if cierre.estado in {"cerrado", "archivado"}]
    movimientos_activos = [movimiento for movimiento in movimientos if movimiento.estado != "anulado"]

    controles = [
        _control(
            "Frontera tenant",
            True,
            "Todos los registros considerados pertenecen a la organizacion y unidad activas.",
            cantidad=len(ventas) + len(movimientos) + len(gestiones) + len(cierres) + len(lotes),
        ),
        _control(
            "Conciliacion local",
            conciliacion["aprobada"],
            "La certificacion de conciliacion no presenta bloqueos."
            if conciliacion["aprobada"] else "La conciliacion conserva bloqueos pendientes.",
            cantidad=conciliacion["resumen"]["bloqueos"],
        ),
        _control(
            "Integridad de lotes",
            not lotes_inconsistentes and not huellas_duplicadas,
            "Las huellas son unicas y los lotes confirmados conservan todos sus movimientos."
            if not lotes_inconsistentes and not huellas_duplicadas
            else "Hay lotes confirmados incompletos o huellas repetidas.",
            cantidad=len(lotes_inconsistentes) + huellas_duplicadas,
        ),
        _control(
            "Cierre auditable",
            bool(cierres_terminales),
            "Existe al menos un cierre terminado para respaldar el periodo."
            if cierres_terminales else "Todavia no existe un cierre cerrado o archivado.",
            cantidad=len(cierres_terminales),
        ),
        _control(
            "Legajo de rendicion",
            legajo["lista_para_archivar"],
            "El legajo esta listo para archivo interno."
            if legajo["lista_para_archivar"] else "El legajo conserva pendientes internos.",
            cantidad=len(legajo["bloqueos"]),
        ),
        _control(
            "Frontera externa",
            True,
            "No se ejecutan cobros, devoluciones, transferencias, API ni webhooks.",
            cantidad=0,
        ),
    ]
    bloqueos = [control["detalle"] for control in controles if not control["aprobado"]]
    advertencias = []
    if not lotes:
        advertencias.append("No hay lotes de extractos MP importados para esta unidad.")
    if not movimientos_activos:
        advertencias.append("No hay movimientos activos para evaluar.")

    return {
        "formato": "certificacion-integral-mp-v1",
        "tenant": {
            "organizacion_id": organizacion_id,
            "unidad_negocio_id": unidad_negocio_id,
        },
        "aprobada": not bloqueos,
        "estado": "aprobada" if not bloqueos else "bloqueada",
        "controles": controles,
        "bloqueos": bloqueos,
        "advertencias": advertencias,
        "resumen": {
            "ventas": len(ventas),
            "movimientos": len(movimientos),
            "movimientos_activos": len(movimientos_activos),
            "gestiones": len(gestiones),
            "cierres": len(cierres),
            "cierres_terminales": len(cierres_terminales),
            "lotes": len(lotes),
            "lotes_confirmados": sum(lote.estado == "confirmado" for lote in lotes),
            "lotes_anulados": sum(lote.estado == "anulado" for lote in lotes),
            "acciones_externas": 0,
        },
        "conciliacion": conciliacion,
        "control_periodico": control_periodico,
        "legajo": legajo,
        "puede_ejecutar": False,
    }


def exportar_certificacion_integral(reporte):
    """Arma un expediente ZIP en memoria con manifiesto SHA-256."""
    evidencia = json.dumps(
        reporte, ensure_ascii=False, sort_keys=True, indent=2, default=str,
    ).encode("utf-8")
    resumen = {
        "formato": reporte["formato"],
        "tenant": reporte["tenant"],
        "estado": reporte["estado"],
        "bloqueos": reporte["bloqueos"],
        "advertencias": reporte["advertencias"],
        "resumen": reporte["resumen"],
        "controles": reporte["controles"],
        "puede_ejecutar": False,
    }
    resumen_bytes = json.dumps(
        resumen, ensure_ascii=False, sort_keys=True, indent=2,
    ).encode("utf-8")
    archivos = {
        "certificacion_integral.json": evidencia,
        "resumen_ejecutivo.json": resumen_bytes,
        "LEEME.txt": (
            "Certificacion local de preparacion Mercado Pago.\n"
            "No ejecuta cobros, devoluciones, transferencias, API ni webhooks.\n"
        ).encode("utf-8"),
    }
    manifiesto = {
        "formato": "manifiesto-certificacion-integral-mp-v1",
        "acciones_externas": 0,
        "archivos": {
            nombre: hashlib.sha256(contenido).hexdigest()
            for nombre, contenido in archivos.items()
        },
    }
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as paquete:
        for nombre, contenido in archivos.items():
            paquete.writestr(nombre, contenido)
        paquete.writestr(
            "manifiesto.json",
            json.dumps(manifiesto, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
        )
    salida.seek(0)
    return salida
