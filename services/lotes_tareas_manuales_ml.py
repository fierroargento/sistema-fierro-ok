"""Decisiones masivas atomicas y evidencia de tareas humanas ML."""

import csv
import io

from services.tareas_manuales_ml import decidir_tarea


MAPA = {
    "aprobar": "aprobada", "rechazar": "rechazada",
    "completar_manual": "completada_manual", "archivar": "archivada",
}


def previsualizar_lote(tareas, accion, comprobante, *, organizacion_id, unidad_negocio_id, vigencias):
    tareas = list(tareas or [])
    if not tareas: raise ValueError("Selecciona al menos una tarea.")
    if accion not in MAPA: raise ValueError("La decision masiva no es valida.")
    if len({t.id for t in tareas}) != len(tareas): raise ValueError("La seleccion contiene tareas repetidas.")
    seleccion = {t.id for t in tareas}
    errores = []
    for tarea in tareas:
        if tarea.organizacion_id != organizacion_id or tarea.unidad_negocio_id != unidad_negocio_id:
            errores.append(f"Tarea #{tarea.id}: fuera del tenant activo."); continue
        if tarea.puede_ejecutar: errores.append(f"Tarea #{tarea.id}: contrato externo invalido.")
        if accion in {"aprobar", "completar_manual"} and not vigencias.get(tarea.lote_diagnostico_id, False):
            errores.append(f"Tarea #{tarea.id}: diagnostico obsoleto.")
        esperado = {"aprobar":"preparada", "rechazar":"preparada", "completar_manual":"aprobada"}.get(accion)
        if esperado and tarea.estado != esperado: errores.append(f"Tarea #{tarea.id}: estado {tarea.estado} no permitido.")
        if accion == "archivar" and tarea.estado not in {"rechazada", "obsoleta", "completada_manual"}:
            errores.append(f"Tarea #{tarea.id}: no se puede archivar.")
        if accion in {"rechazar", "completar_manual", "archivar"} and not str(comprobante or "").strip():
            errores.append(f"Tarea #{tarea.id}: falta motivo o comprobante.")
        if accion == "completar_manual" and tarea.depende_de is not None:
            if tarea.depende_de.estado != "completada_manual" and tarea.depende_de.id not in seleccion:
                errores.append(f"Tarea #{tarea.id}: falta completar la dependencia #{tarea.depende_de.id}.")
    return {"tareas": sorted(tareas, key=lambda t: (t.publicacion_id, t.orden, t.id)), "accion": accion,
            "destino": MAPA[accion], "errores": errores, "puede_aplicar": not errores,
            "puede_ejecutar": False}


def aplicar_lote(previsualizacion, comprobante, *, usuario, vigencias, EventoTareaManualML, db_session):
    if not previsualizacion.get("puede_aplicar") or previsualizacion.get("errores"):
        raise ValueError("El lote no supero la prevalidacion atomica.")
    accion = previsualizacion["accion"]
    for tarea in previsualizacion["tareas"]:
        anterior = tarea.estado
        decidir_tarea(tarea, accion, comprobante, usuario=usuario,
                      lote_vigente=vigencias.get(tarea.lote_diagnostico_id, False),
                      db_session=db_session, commit=False)
        db_session.add(EventoTareaManualML(
            organizacion_id=tarea.organizacion_id, unidad_negocio_id=tarea.unidad_negocio_id,
            tarea_manual_id=tarea.id, estado_anterior=anterior, estado_nuevo=tarea.estado,
            comprobante=str(comprobante or "").strip() or None,
            username=getattr(usuario, "username", None),
        ))
    db_session.commit()
    return {"actualizadas": len(previsualizacion["tareas"]), "estado": previsualizacion["destino"], "puede_ejecutar": False}


def exportar_evidencia(tareas):
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida)
    escritor.writerow(["tarea_id", "publicacion", "orden", "accion", "estado", "evento", "anterior", "nuevo", "usuario", "comprobante", "fecha"])
    for tarea in tareas:
        eventos = sorted(getattr(tarea, "eventos", []) or [], key=lambda e: (str(e.fecha_evento), e.id or 0))
        if not eventos: escritor.writerow([tarea.id, tarea.publicacion_id, tarea.orden, tarea.tipo_accion, tarea.estado, "", "", "", "", "", ""])
        for evento in eventos:
            escritor.writerow([tarea.id, tarea.publicacion_id, tarea.orden, tarea.tipo_accion, tarea.estado, evento.id, evento.estado_anterior or "", evento.estado_nuevo, evento.username or "", evento.comprobante or "", evento.fecha_evento])
    return io.BytesIO(salida.getvalue().encode("utf-8-sig"))
