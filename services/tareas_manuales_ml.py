"""Prepara y controla tareas humanas ML sin API, OAuth ni transporte."""

import csv
import hashlib
import io
import json

from services.fechas import ahora_utc_naive


def _serializar(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def especificaciones_lote(lote):
    if lote is None or lote.estado != "aprobado" or lote.puede_ejecutar:
        raise ValueError("Solo un diagnostico aprobado y no ejecutable puede preparar tareas.")
    resultado = json.loads(lote.resultado_json)
    salida = []
    for fila in resultado.get("control", {}).get("resultados", []):
        publicacion = fila.get("publicacion") or {}
        anterior = None
        for accion in fila.get("acciones") or []:
            tipo = str(accion.get("accion") or "")
            if tipo not in {"cancelar_promocion", "actualizar_precio"}:
                continue
            snapshot = {
                "lote_id": lote.lote_id, "publicacion_id": publicacion.get("publicacion_id"),
                "sku": publicacion.get("sku"), "tipo_accion": tipo,
                "orden": int(accion.get("orden") or 1),
                "precio_actual_centavos": publicacion.get("precio_centavos"),
                "precio_propuesto_centavos": fila.get("precio_objetivo_centavos"),
                "huella_dependencias": lote.huella_dependencias,
            }
            texto = _serializar(snapshot)
            clave = hashlib.sha256(texto.encode("utf-8")).hexdigest()
            salida.append({**snapshot, "snapshot_json": texto, "clave_idempotencia": clave, "depende_de_clave": anterior})
            anterior = clave
    return salida


def preparar_tareas(lote, *, usuario, TareaManualML, db_session):
    existentes = {x.clave_idempotencia: x for x in TareaManualML.query.filter_by(organizacion_id=lote.organizacion_id).all()}
    creadas, omitidas = [], 0
    for spec in especificaciones_lote(lote):
        if spec["clave_idempotencia"] in existentes:
            omitidas += 1
            continue
        dependencia = existentes.get(spec.pop("depende_de_clave"))
        tarea = TareaManualML(
            organizacion_id=lote.organizacion_id, unidad_negocio_id=lote.unidad_negocio_id,
            lote_diagnostico_id=lote.id, depende_de=dependencia,
            publicacion_id=str(spec.pop("publicacion_id") or ""), sku=spec.pop("sku"),
            huella_origen=lote.huella_dependencias, estado="preparada", puede_ejecutar=False,
            creado_por_username=getattr(usuario, "username", None), **spec,
        )
        db_session.add(tarea); db_session.flush(); creadas.append(tarea)
        existentes[tarea.clave_idempotencia] = tarea
    db_session.commit()
    return {"creadas": creadas, "omitidas": omitidas, "puede_ejecutar": False}


def decidir_tarea(tarea, accion, comprobante, *, usuario, lote_vigente, db_session, commit=True):
    if tarea is None or tarea.puede_ejecutar:
        raise ValueError("La tarea no cumple el contrato interno.")
    accion = str(accion or "").strip().lower(); texto = str(comprobante or "").strip()
    if accion in {"aprobar", "completar_manual"} and not lote_vigente:
        tarea.estado = "obsoleta"; tarea.puede_ejecutar = False
        if commit: db_session.commit()
        return tarea
    if accion == "aprobar" and tarea.estado == "preparada": destino = "aprobada"
    elif accion == "rechazar" and tarea.estado == "preparada" and texto: destino = "rechazada"
    elif accion == "completar_manual" and tarea.estado == "aprobada" and texto:
        if tarea.depende_de is not None and tarea.depende_de.estado != "completada_manual":
            raise ValueError("Primero debe completarse la tarea precedente.")
        destino = "completada_manual"
    elif accion == "archivar" and tarea.estado in {"rechazada", "obsoleta", "completada_manual"} and texto: destino = "archivada"
    else: raise ValueError("La transicion o el comprobante no son validos.")
    tarea.estado = destino; tarea.comprobante_manual = texto or None
    tarea.decidido_por_username = getattr(usuario, "username", None)
    tarea.fecha_decision = ahora_utc_naive(); tarea.puede_ejecutar = False
    if commit: db_session.commit()
    return tarea


def exportar_tareas(tareas):
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida)
    escritor.writerow(["publicacion", "sku", "orden", "accion_manual", "precio_actual", "precio_propuesto", "estado", "comprobante"])
    for t in tareas:
        escritor.writerow([t.publicacion_id, t.sku or "", t.orden, t.tipo_accion, t.precio_actual_centavos or "", t.precio_propuesto_centavos or "", t.estado, t.comprobante_manual or ""])
    return io.BytesIO(salida.getvalue().encode("utf-8-sig"))
