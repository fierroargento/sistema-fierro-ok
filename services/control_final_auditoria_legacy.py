"""Control final, firmado y de solo lectura para asignaciones de auditoría legacy."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json


def _evidencia(propuesta):
    try:
        valor = json.loads(propuesta.evidencia_json)
        return valor if isinstance(valor, dict) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def controlar_asignaciones(organizacion_id, propuestas):
    organizacion_id = int(organizacion_id)
    observaciones = []
    filas = []
    estados = Counter()
    vistos = set()
    for propuesta in propuestas:
        estados[str(propuesta.estado)] += 1
        evidencia = _evidencia(propuesta)
        errores = []
        if propuesta.organizacion_propuesta_id != organizacion_id:
            errores.append("tenant_cruzado")
        if propuesta.auditoria_id in vistos:
            errores.append("auditoria_duplicada")
        vistos.add(propuesta.auditoria_id)
        if evidencia is None:
            errores.append("evidencia_invalida")
        else:
            if evidencia.get("organizacion_propuesta_id") != propuesta.organizacion_propuesta_id:
                errores.append("evidencia_tenant_inconsistente")
            if evidencia.get("estado") != "asignable":
                errores.append("evidencia_no_asignable")
        tenant_auditoria = getattr(propuesta.auditoria, "organizacion_id", None)
        if propuesta.estado == "aplicada" and tenant_auditoria != organizacion_id:
            errores.append("aplicacion_inconsistente")
        if propuesta.estado != "aplicada" and tenant_auditoria == organizacion_id:
            errores.append("asignacion_fuera_del_flujo")
        observaciones.extend({"propuesta_id": propuesta.id, "codigo": codigo} for codigo in errores)
        filas.append({"propuesta_id": propuesta.id, "auditoria_id": propuesta.auditoria_id,
                      "estado": propuesta.estado, "tenant_auditoria": tenant_auditoria,
                      "resultado": "observada" if errores else "valida"})
    cuerpo = {"tipo": "control_final_auditoria_legacy", "version": 1,
              "organizacion_id": organizacion_id, "total": len(filas),
              "estados": dict(sorted(estados.items())), "observaciones": observaciones,
              "asignaciones": filas, "aprobado": not observaciones,
              "solo_lectura": True, "auditorias_modificadas": 0}
    canonico = json.dumps(cuerpo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cuerpo["firma_sha256"] = sha256(canonico.encode("utf-8")).hexdigest()
    cuerpo["generado_utc"] = datetime.now(timezone.utc).isoformat()
    return cuerpo


def obtener_control_tenant(organizacion_id, *, AsignacionTenantAuditoria, limite=1000):
    propuestas = (AsignacionTenantAuditoria.query
                  .filter_by(organizacion_propuesta_id=int(organizacion_id))
                  .order_by(AsignacionTenantAuditoria.id.asc())
                  .limit(max(1, min(int(limite), 1000))).all())
    return controlar_asignaciones(organizacion_id, propuestas)


def exportar_control(control):
    return BytesIO(json.dumps(control, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
