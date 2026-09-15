"""Lecturas de auditoría limitadas explícitamente al tenant activo."""

import hashlib
import io
import json


def obtener_auditorias_tenant(organizacion_id, *, Auditoria, limite=300):
    limite = max(1, min(int(limite), 1000))
    return (
        Auditoria.query
        .filter(Auditoria.organizacion_id == int(organizacion_id))
        .order_by(Auditoria.fecha.desc(), Auditoria.id.desc())
        .limit(limite)
        .all()
    )


def diagnosticar_auditorias_tenant(organizacion_id, auditorias):
    propias = [x for x in auditorias if x.organizacion_id == organizacion_id]
    hallazgos = []
    ids = set()
    ultima = None
    for registro in propias:
        if registro.id in ids:
            hallazgos.append({"codigo": "registro_duplicado", "id": registro.id})
        ids.add(registro.id)
        if not str(getattr(registro, "accion", "") or "").strip():
            hallazgos.append({"codigo": "accion_vacia", "id": registro.id})
        fecha = getattr(registro, "fecha", None)
        if ultima is not None and fecha is not None and fecha > ultima:
            hallazgos.append({"codigo": "secuencia_temporal_invalida", "id": registro.id})
        if fecha is not None:
            ultima = fecha
    resumen = {"registros": len(propias), "hallazgos": len(hallazgos), "legacy_sin_tenant_incluidos": 0}
    base = {"organizacion_id": organizacion_id, "resumen": resumen, "hallazgos": hallazgos, "solo_lectura": True}
    base["huella"] = hashlib.sha256(json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return base


def construir_evidencia_auditoria(organizacion_id, auditorias):
    diagnostico = diagnosticar_auditorias_tenant(organizacion_id, auditorias)
    registros = []
    for registro in auditorias:
        if registro.organizacion_id != organizacion_id:
            continue
        registros.append({
            "id": registro.id,
            "usuario_id": getattr(registro, "usuario_id", None),
            "username": getattr(registro, "username", None),
            "rol": getattr(registro, "rol", None),
            "accion": registro.accion,
            "entidad": getattr(registro, "entidad", None),
            "entidad_id": getattr(registro, "entidad_id", None),
            "detalle": getattr(registro, "detalle", None),
            "fecha": registro.fecha.isoformat() if getattr(registro, "fecha", None) else None,
            "metodo": getattr(registro, "metodo", None),
            "path": getattr(registro, "path", None),
        })
    evidencia = {
        "organizacion_id": organizacion_id,
        "modo": "solo_lectura",
        "diagnostico": diagnostico,
        "registros": registros,
        "controles": {
            "legacy_sin_tenant_incluidos": 0,
            "datos_modificados": 0,
            "datos_eliminados": 0,
            "acciones_externas": 0,
            "escrituras": 0,
        },
    }
    evidencia["huella_evidencia"] = hashlib.sha256(
        json.dumps(evidencia, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return evidencia


def exportar_evidencia(evidencia):
    return io.BytesIO(json.dumps(evidencia, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
