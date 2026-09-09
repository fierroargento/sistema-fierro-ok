"""Gestiona diagnosticos ML internos; aprobar nunca habilita ejecucion externa."""

import hashlib
import json

from services.consolidacion_offline_ml import consolidar_snapshot_ml
from services.fechas import ahora_utc_naive


TRANSICIONES = {
    "enviar_revision": ({"preparado"}, "revision"),
    "aprobar": ({"revision"}, "aprobado"),
    "rechazar": ({"revision"}, "rechazado"),
    "archivar": ({"preparado", "aprobado", "rechazado", "obsoleto"}, "archivado"),
}


def _json(datos):
    return json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def huella_dependencias(control):
    filas = []
    for item in control.get("resultados") or []:
        publicacion = item.get("publicacion") or {}
        filas.append({
            "identidad": publicacion.get("identidad"),
            "costo_version_id": item.get("costo_version_id"),
            "regla_economica_id": item.get("regla_economica_id"),
            "regla_canal_id": item.get("regla_canal_id"),
            "catalogo_producto_id": item.get("catalogo_producto_id"),
            "piso_minimo_centavos": item.get("piso_minimo_centavos"),
            "piso_objetivo_centavos": item.get("piso_objetivo_centavos"),
            "precio_objetivo_centavos": item.get("precio_objetivo_centavos"),
            "estado": item.get("estado"),
        })
    material = _json(sorted(filas, key=lambda fila: str(fila["identidad"])))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def registrar_lote(resultado, *, vinculo_canal_id, usuario,
                   LoteDiagnosticoML, EventoLoteDiagnosticoML, db_session):
    lote = resultado["lote"]
    control = resultado["control"]
    organizacion_id = int((lote["snapshot"].get("resultados") or [{}])[0].get("organizacion_id") or 0)
    unidad_id = int((lote["snapshot"].get("resultados") or [{}])[0].get("unidad_negocio_id") or 0)
    if not organizacion_id or not unidad_id:
        raise ValueError("El lote no contiene una identidad tenant valida.")
    existente = LoteDiagnosticoML.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        cuenta_codigo=(lote["snapshot"].get("resultados") or [{}])[0].get("cuenta_codigo"),
        lote_id=lote["lote_id"],
    ).first()
    if existente is not None:
        return existente, False
    if lote["errores_lote"]:
        raise ValueError("El lote tiene errores y no puede guardarse.")
    registro = LoteDiagnosticoML(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        vinculo_canal_id=int(vinculo_canal_id),
        lista_precio_id=int(control["lista_precio_id"]),
        cuenta_codigo=(lote["snapshot"].get("resultados") or [{}])[0]["cuenta_codigo"],
        lote_id=lote["lote_id"], huella_dependencias=huella_dependencias(control),
        firmas_secciones_json=_json(lote["firmas_secciones"]),
        snapshot_json=_json(lote["snapshot"]), resultado_json=_json(resultado),
        estado="preparado", puede_ejecutar=False,
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None),
    )
    db_session.add(registro)
    db_session.flush()
    db_session.add(EventoLoteDiagnosticoML(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_id,
        lote_diagnostico_id=registro.id, estado_anterior=None,
        estado_nuevo="preparado", motivo="Registro manual del diagnostico offline",
        usuario_id=getattr(usuario, "id", None), username=getattr(usuario, "username", None),
    ))
    db_session.commit()
    return registro, True


def diagnosticar_vigencia(lote, filas_control):
    snapshot = json.loads(lote.snapshot_json)
    actual = consolidar_snapshot_ml(
        snapshot, filas_control, lista_precio_id=lote.lista_precio_id,
    )
    huella_actual = huella_dependencias(actual)
    return {
        "vigente": huella_actual == lote.huella_dependencias,
        "huella_guardada": lote.huella_dependencias,
        "huella_actual": huella_actual,
        "control_actual": actual,
    }


def decidir_lote(lote, accion, motivo, *, usuario, filas_control,
                 EventoLoteDiagnosticoML, db_session):
    if lote is None or lote.puede_ejecutar:
        raise ValueError("El lote no cumple el contrato interno.")
    accion = str(accion or "").strip().lower()
    if accion not in TRANSICIONES:
        raise ValueError("La decision no es valida.")
    origenes, destino = TRANSICIONES[accion]
    if lote.estado not in origenes:
        raise ValueError("La transicion no corresponde al estado actual.")
    vigencia = diagnosticar_vigencia(lote, filas_control)
    anterior = lote.estado
    razon = str(motivo or "").strip()
    if accion in {"enviar_revision", "aprobar"} and not vigencia["vigente"]:
        destino = "obsoleto"
        razon = razon or "Cambió el costo, la regla económica o la política del canal."
    elif accion == "aprobar":
        resultado = json.loads(lote.resultado_json)
        if resultado["lote"]["errores_lote"] or resultado["control"]["resumen"]["bloqueadas"]:
            raise ValueError("Un lote con errores o publicaciones bloqueadas no puede aprobarse.")
    if accion in {"rechazar", "archivar"} and not razon:
        raise ValueError("La decision requiere un motivo.")
    lote.estado = destino
    lote.motivo_decision = razon or None
    lote.revisado_por_usuario_id = getattr(usuario, "id", None)
    lote.revisado_por_username = getattr(usuario, "username", None)
    lote.fecha_revision = ahora_utc_naive()
    lote.puede_ejecutar = False
    db_session.add(EventoLoteDiagnosticoML(
        organizacion_id=lote.organizacion_id, unidad_negocio_id=lote.unidad_negocio_id,
        lote_diagnostico_id=lote.id, estado_anterior=anterior,
        estado_nuevo=destino, motivo=razon or None,
        usuario_id=getattr(usuario, "id", None), username=getattr(usuario, "username", None),
    ))
    db_session.commit()
    return {"lote": lote, "vigencia": vigencia, "estado": destino, "puede_ejecutar": False}
