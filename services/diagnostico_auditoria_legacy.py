"""Diagnóstico preparatorio de auditorías legacy sin identidad tenant."""

import hashlib
import io
import json


def obtener_contexto_legacy(*, Auditoria, UsuarioSistema, UsuarioOrganizacion, limite=1000):
    limite = max(1, min(int(limite), 5000))
    auditorias = (
        Auditoria.query
        .filter(Auditoria.organizacion_id.is_(None))
        .order_by(Auditoria.fecha.asc(), Auditoria.id.asc())
        .limit(limite)
        .all()
    )
    usernames = {str(x.username or "").strip().lower() for x in auditorias if x.username}
    membresias = [] if not usernames else (
        UsuarioOrganizacion.query
        .join(UsuarioSistema)
        .filter(UsuarioOrganizacion.activa.is_(True))
        .filter(UsuarioSistema.username.in_(usernames))
        .order_by(UsuarioOrganizacion.usuario_id.asc(), UsuarioOrganizacion.organizacion_id.asc())
        .all()
    )
    return auditorias, membresias


def clasificar_auditorias_legacy(auditorias, membresias):
    organizaciones_por_username = {}
    for membresia in membresias:
        username = str(getattr(getattr(membresia, "usuario", None), "username", "") or "").strip().lower()
        if username and membresia.activa:
            organizaciones_por_username.setdefault(username, set()).add(int(membresia.organizacion_id))
    resultados = []
    for auditoria in auditorias:
        if getattr(auditoria, "organizacion_id", None) is not None:
            continue
        username = str(getattr(auditoria, "username", "") or "").strip().lower()
        candidatos = sorted(organizaciones_por_username.get(username, set()))
        estado = "asignable" if len(candidatos) == 1 else "ambiguo" if len(candidatos) > 1 else "sin_candidato"
        resultados.append({
            "auditoria_id": auditoria.id,
            "username": username or None,
            "accion": getattr(auditoria, "accion", None),
            "entidad": getattr(auditoria, "entidad", None),
            "entidad_id": getattr(auditoria, "entidad_id", None),
            "fecha": auditoria.fecha.isoformat() if getattr(auditoria, "fecha", None) else None,
            "organizaciones_candidatas": candidatos,
            "organizacion_propuesta_id": candidatos[0] if estado == "asignable" else None,
            "estado": estado,
        })
    resumen = {
        "legacy": len(resultados),
        "asignables": sum(x["estado"] == "asignable" for x in resultados),
        "ambiguas": sum(x["estado"] == "ambiguo" for x in resultados),
        "sin_candidato": sum(x["estado"] == "sin_candidato" for x in resultados),
        "asignaciones_aplicadas": 0,
    }
    resultado = {
        "modo": "diagnostico_sin_escrituras",
        "resumen": resumen,
        "auditorias": resultados,
        "controles": {"backfill_automatico": False, "auditorias_modificadas": 0, "auditorias_eliminadas": 0, "acciones_externas": 0, "escrituras": 0},
    }
    resultado["huella_diagnostico"] = hashlib.sha256(json.dumps(resultado, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return resultado


def exportar_diagnostico(resultado):
    return io.BytesIO(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
