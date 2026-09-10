"""Certifica en solo lectura la preparacion operativa ML desconectada."""

import io
import json


def certificar_operacion_ml(lotes, tareas, *, organizacion_id, unidad_negocio_id, vigencias):
    lotes = list(lotes or []); tareas = list(tareas or [])
    bloqueos, advertencias = [], []
    lote_por_id = {l.id: l for l in lotes}
    resumen = {
        "lotes": len(lotes), "tareas": len(tareas), "preparadas": 0,
        "aprobadas": 0, "completadas": 0, "obsoletas": 0,
        "eventos": 0, "bloqueos": 0, "advertencias": 0,
    }
    for lote in lotes:
        if lote.organizacion_id != organizacion_id or lote.unidad_negocio_id != unidad_negocio_id:
            bloqueos.append(f"Lote #{lote.id} fuera del tenant activo.")
        if bool(getattr(lote, "puede_ejecutar", False)):
            bloqueos.append(f"Lote #{lote.id} habilita ejecucion externa.")
    for tarea in tareas:
        resumen["eventos"] += len(getattr(tarea, "eventos", []) or [])
        clave = {"preparada":"preparadas", "aprobada":"aprobadas", "completada_manual":"completadas", "obsoleta":"obsoletas"}.get(tarea.estado)
        if clave: resumen[clave] += 1
        if tarea.organizacion_id != organizacion_id or tarea.unidad_negocio_id != unidad_negocio_id:
            bloqueos.append(f"Tarea #{tarea.id} fuera del tenant activo.")
        if bool(getattr(tarea, "puede_ejecutar", False)):
            bloqueos.append(f"Tarea #{tarea.id} habilita ejecucion externa.")
        lote = lote_por_id.get(tarea.lote_diagnostico_id)
        if lote is None: bloqueos.append(f"Tarea #{tarea.id} no tiene diagnostico del tenant.")
        if tarea.estado in {"preparada", "aprobada"} and not vigencias.get(tarea.lote_diagnostico_id, False):
            bloqueos.append(f"Tarea #{tarea.id} depende de un diagnostico obsoleto.")
        dependencia = getattr(tarea, "depende_de", None)
        if dependencia is not None:
            if dependencia.organizacion_id != tarea.organizacion_id or dependencia.unidad_negocio_id != tarea.unidad_negocio_id:
                bloqueos.append(f"Tarea #{tarea.id} cruza una dependencia tenant.")
            if dependencia.lote_diagnostico_id != tarea.lote_diagnostico_id or dependencia.orden >= tarea.orden:
                bloqueos.append(f"Tarea #{tarea.id} tiene una dependencia invalida.")
            if tarea.estado == "completada_manual" and dependencia.estado != "completada_manual":
                bloqueos.append(f"Tarea #{tarea.id} se completo antes que su dependencia.")
        if tarea.estado == "completada_manual" and not str(getattr(tarea, "comprobante_manual", "") or "").strip():
            bloqueos.append(f"Tarea #{tarea.id} no tiene comprobante manual.")
        if tarea.estado not in {"preparada"} and not (getattr(tarea, "eventos", []) or []):
            advertencias.append(f"Tarea #{tarea.id} no tiene evento historico; puede ser anterior a la certificacion.")
    resumen["bloqueos"] = len(bloqueos); resumen["advertencias"] = len(advertencias)
    controles = {
        "tenant_aislado": not any("tenant" in x for x in bloqueos),
        "ejecucion_externa_bloqueada": not any("ejecucion externa" in x for x in bloqueos),
        "dependencias_validas": not any("dependencia" in x for x in bloqueos),
        "vigencia_valida": not any("obsoleto" in x for x in bloqueos),
        "comprobantes_validos": not any("comprobante" in x for x in bloqueos),
    }
    return {"aprobada": not bloqueos, "controles": controles, "resumen": resumen,
            "bloqueos": bloqueos, "advertencias": advertencias,
            "acciones_externas": 0, "escrituras": 0}


def exportar_certificacion_ml(certificacion):
    contenido = json.dumps(certificacion, ensure_ascii=False, sort_keys=True, indent=2, default=str)
    return io.BytesIO(contenido.encode("utf-8"))
