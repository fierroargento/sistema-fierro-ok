"""Registro y revision interna de diagnosticos Tienda Nube offline."""

import hashlib
import io
import json

from services.fechas import ahora_utc_naive


TRANSICIONES = {
    "enviar_revision": ({"preparado"}, "revision"),
    "aprobar": ({"revision"}, "aprobado"),
    "rechazar": ({"revision"}, "rechazado"),
    "archivar": ({"preparado", "aprobado", "rechazado"}, "archivado"),
}


def huella_documento(contenido):
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    return hashlib.sha256(bytes(contenido)).hexdigest()


def registrar_lote(resultado, contenido, nombre_archivo, *, usuario,
                   LoteDiagnosticoTiendaNube,
                   EventoLoteDiagnosticoTiendaNube, db_session):
    contexto = resultado["contexto"]
    resumen = resultado["resumen"]
    huella = huella_documento(contenido)
    existente = LoteDiagnosticoTiendaNube.query.filter_by(
        organizacion_id=contexto["organizacion_id"],
        unidad_negocio_id=contexto["unidad_negocio_id"],
        tienda_nube_cuenta_id=contexto["cuenta_id"],
        huella_documento=huella,
    ).first()
    if existente is not None:
        return existente, False
    registro = LoteDiagnosticoTiendaNube(
        organizacion_id=contexto["organizacion_id"],
        unidad_negocio_id=contexto["unidad_negocio_id"],
        vinculo_canal_id=contexto["vinculo_id"],
        tienda_nube_cuenta_id=contexto["cuenta_id"],
        store_id_snapshot=contexto["store_id"],
        nombre_archivo=str(nombre_archivo or "fixture.json")[:255],
        huella_documento=huella,
        evidencia_json=json.dumps(resultado, ensure_ascii=False, sort_keys=True, default=str),
        filas=resumen["filas"], aptas=resumen["aptas"],
        bloqueadas=resumen["bloqueadas"], errores=resumen["errores"],
        estado="preparado", puede_ejecutar=False,
        creado_por_usuario_id=getattr(usuario, "id", None),
        creado_por_username=getattr(usuario, "username", None),
    )
    try:
        db_session.add(registro)
        db_session.flush()
        db_session.add(EventoLoteDiagnosticoTiendaNube(
            organizacion_id=registro.organizacion_id,
            unidad_negocio_id=registro.unidad_negocio_id,
            lote_diagnostico_id=registro.id,
            estado_anterior=None, estado_nuevo="preparado",
            motivo="Diagnostico generado desde archivo local",
            usuario_id=getattr(usuario, "id", None),
            username=getattr(usuario, "username", None),
        ))
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return registro, True


def decidir_lote(lote, accion, motivo, *, organizacion_id, unidad_negocio_id,
                 usuario, EventoLoteDiagnosticoTiendaNube, db_session):
    if lote is None or lote.organizacion_id != organizacion_id or lote.unidad_negocio_id != unidad_negocio_id:
        raise ValueError("El lote no pertenece a la unidad activa.")
    if lote.puede_ejecutar:
        raise ValueError("El lote incumple el contrato desconectado.")
    accion = str(accion or "").strip().lower()
    if accion not in TRANSICIONES:
        raise ValueError("La decision del lote no es valida.")
    origenes, destino = TRANSICIONES[accion]
    if lote.estado not in origenes:
        raise ValueError("La transicion no corresponde al estado actual.")
    razon = str(motivo or "").strip()
    if accion in {"rechazar", "archivar"} and not razon:
        raise ValueError("La decision requiere un motivo.")
    if accion == "aprobar" and (lote.bloqueadas or lote.errores):
        raise ValueError("Un lote con pedidos bloqueados o errores no puede aprobarse.")
    anterior = lote.estado
    lote.estado = destino
    lote.motivo_decision = razon or None
    lote.revisado_por_usuario_id = getattr(usuario, "id", None)
    lote.revisado_por_username = getattr(usuario, "username", None)
    lote.fecha_revision = ahora_utc_naive()
    lote.puede_ejecutar = False
    try:
        db_session.add(EventoLoteDiagnosticoTiendaNube(
            organizacion_id=lote.organizacion_id,
            unidad_negocio_id=lote.unidad_negocio_id,
            lote_diagnostico_id=lote.id,
            estado_anterior=anterior, estado_nuevo=destino,
            motivo=razon or None,
            usuario_id=getattr(usuario, "id", None),
            username=getattr(usuario, "username", None),
        ))
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    return {"lote_id": lote.id, "estado": destino, "puede_ejecutar": False, "acciones_externas": 0}


def resumir_bandeja(lotes, *, organizacion_id, unidad_negocio_id):
    propios = [lote for lote in (lotes or []) if lote.organizacion_id == organizacion_id and lote.unidad_negocio_id == unidad_negocio_id]
    propios.sort(key=lambda lote: (lote.fecha_creacion, lote.id), reverse=True)
    return {
        "lotes": propios, "total": len(propios),
        "preparados": sum(lote.estado == "preparado" for lote in propios),
        "revision": sum(lote.estado == "revision" for lote in propios),
        "aprobados": sum(lote.estado == "aprobado" for lote in propios),
        "bloqueados": sum(bool(lote.bloqueadas or lote.errores) for lote in propios),
        "acciones_externas": 0,
    }


def exportar_evidencia_lote(lote, *, organizacion_id, unidad_negocio_id):
    if lote is None or lote.organizacion_id != organizacion_id or lote.unidad_negocio_id != unidad_negocio_id:
        raise ValueError("El lote no pertenece a la unidad activa.")
    evidencia = json.loads(lote.evidencia_json)
    salida = {
        "lote": {
            "id": lote.id, "estado": lote.estado,
            "store_id": lote.store_id_snapshot,
            "huella_documento": lote.huella_documento,
            "puede_ejecutar": False, "acciones_externas": 0,
        },
        "evidencia": evidencia,
    }
    return io.BytesIO(json.dumps(salida, ensure_ascii=False, sort_keys=True, indent=2, default=str).encode("utf-8"))
