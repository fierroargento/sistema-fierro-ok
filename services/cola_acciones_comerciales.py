"""Planifica y decide acciones comerciales internas; nunca ejecuta canales."""

import hashlib
import json

from services.fechas import ahora_utc_naive


def _snapshot(fila, tipo_accion):
    actual = fila.get("actual")
    promocion = fila.get("promocion")
    return {
        "tipo_accion": tipo_accion,
        "lista_precio_id": fila["regla_canal"].lista_precio_id,
        "catalogo_producto_id": fila["inclusion"].id,
        "producto_id": fila["costo"].producto_id,
        "costo_version_id": getattr(fila["costo"], "id", None),
        "regla_canal_id": getattr(fila["regla_canal"], "id", None),
        "promocion_observacion_id": getattr(promocion, "id", None),
        "precio_actual_centavos": actual["precio_final_centavos"] if actual else None,
        "precio_propuesto_centavos": fila["propuesto"]["precio_final_centavos"],
        "piso_minimo_centavos": fila["minimo"]["piso_liquidacion_centavos"],
        "piso_objetivo_centavos": fila["objetivo"]["piso_liquidacion_centavos"],
        "estado_control": fila["estado_control"],
    }


def _huella(snapshot):
    texto = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return texto, hashlib.sha256(texto.encode("utf-8")).hexdigest()


def planificar_fila(fila):
    recomendacion = fila.get("accion_recomendada")
    if recomendacion in {"sin_accion", "mantener_promocion", "completar_catalogo"}: return []
    tipos = (
        ["cancelar_promocion", "actualizar_precio"]
        if recomendacion == "cancelar_promocion_antes_de_actualizar"
        else ["actualizar_precio"]
    )
    resultado = []
    for orden, tipo in enumerate(tipos, start=1):
        snapshot = _snapshot(fila, tipo); texto, huella = _huella(snapshot)
        resultado.append({
            "tipo_accion": tipo, "orden": orden, "snapshot_json": texto,
            "huella_calculo": huella,
            "clave_idempotencia": hashlib.sha256(
                f'{fila["regla_canal"].lista_precio_id}:{fila["inclusion"].id}:{tipo}:{huella}'.encode("utf-8")
            ).hexdigest(),
            "precio_actual_centavos": snapshot["precio_actual_centavos"],
            "precio_propuesto_centavos": snapshot["precio_propuesto_centavos"],
        })
    return resultado


def crear_propuestas(filas, *, organizacion_id, unidad_negocio_id, usuario,
                     PropuestaAccionComercial, db_session):
    creadas = []; omitidas = 0
    existentes = {
        item.clave_idempotencia: item for item in
        PropuestaAccionComercial.query.filter_by(organizacion_id=organizacion_id).all()
    }
    for fila in filas:
        dependencia = None
        for especificacion in planificar_fila(fila):
            if especificacion["clave_idempotencia"] in existentes:
                omitidas += 1
                existente = existentes[especificacion["clave_idempotencia"]]
                if existente.tipo_accion == "cancelar_promocion": dependencia = existente
                continue
            propuesta = PropuestaAccionComercial(
                organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
                lista_precio_id=fila["regla_canal"].lista_precio_id,
                catalogo_producto_id=fila["inclusion"].id,
                promocion_observacion_id=getattr(fila.get("promocion"), "id", None),
                depende_de=dependencia, puede_ejecutar=False, estado="preparada",
                creado_por_usuario_id=getattr(usuario, "id", None),
                creado_por_username=getattr(usuario, "username", None),
                **especificacion,
            )
            db_session.add(propuesta); creadas.append(propuesta); existentes[propuesta.clave_idempotencia] = propuesta
            if propuesta.tipo_accion == "cancelar_promocion": dependencia = propuesta
    db_session.commit()
    return {"creadas": creadas, "omitidas": omitidas}


def propuesta_esta_vigente(propuesta, fila_actual):
    if propuesta is None or fila_actual is None: return False
    return any(
        item["tipo_accion"] == propuesta.tipo_accion
        and item["huella_calculo"] == propuesta.huella_calculo
        for item in planificar_fila(fila_actual)
    )


def decidir_propuesta(propuesta, accion, motivo, *, usuario, db_session,
                      fila_actual=None):
    if propuesta is None or propuesta.puede_ejecutar:
        raise ValueError("La propuesta no cumple el contrato interno.")
    accion = str(accion or "").strip().lower(); razon = str(motivo or "").strip()
    destinos = {"aprobar": "aprobada", "rechazar": "rechazada", "archivar": "archivada", "completar_manual": "completada_manual"}
    if accion not in destinos: raise ValueError("La decisión no es válida.")
    if accion in {"aprobar", "completar_manual"} and not propuesta_esta_vigente(propuesta, fila_actual):
        raise ValueError("La propuesta quedo obsoleta porque cambiaron sus datos de origen.")
    if accion in {"aprobar", "rechazar", "archivar"} and propuesta.estado != "preparada":
        raise ValueError("La propuesta ya fue decidida.")
    if accion == "completar_manual":
        if propuesta.estado != "aprobada": raise ValueError("Solo se puede completar manualmente una propuesta aprobada.")
        if propuesta.depende_de is not None and propuesta.depende_de.estado != "completada_manual":
            raise ValueError("Primero debe completarse manualmente la acción anterior.")
    if accion in {"rechazar", "archivar", "completar_manual"} and not razon:
        raise ValueError("Indicá el motivo o comprobante de la decisión.")
    propuesta.estado = destinos[accion]; propuesta.motivo_decision = razon or None
    propuesta.decidido_por_usuario_id = getattr(usuario, "id", None)
    propuesta.decidido_por_username = getattr(usuario, "username", None)
    propuesta.fecha_decision = ahora_utc_naive(); db_session.commit(); return propuesta
