"""Prepara contratos de integracion usando solo entradas manuales o simuladas."""

import hashlib
import json

from services.fechas import ahora_utc_naive


CANALES = {"mercado_libre", "mercado_pago", "tienda_nube", "otro"}
MODOS = {"deshabilitado", "diagnostico", "simulacion"}
TIPOS_EVENTO = {"publicacion", "comision", "envio", "promocion", "venta", "pago", "devolucion"}


def guardar_control(*, organizacion_id, unidad_negocio_id, canal, cuenta_codigo,
                    modo, certificacion_aprobada=False, certificacion_observacion=None,
                    usuario=None, ControlIntegracionCanal, db_session):
    canal = str(canal or "").strip().lower(); cuenta = str(cuenta_codigo or "").strip(); modo = str(modo or "").strip().lower()
    if canal not in CANALES: raise ValueError("El canal no pertenece al contrato normalizado.")
    if modo not in MODOS: raise ValueError("El modo interno no es valido.")
    if not cuenta: raise ValueError("La cuenta interna es obligatoria.")
    control = ControlIntegracionCanal.query.filter_by(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, canal=canal, cuenta_codigo=cuenta).first()
    if control is None:
        control = ControlIntegracionCanal(organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id, canal=canal, cuenta_codigo=cuenta)
        db_session.add(control)
    control.modo = modo
    control.recepcion_externa_habilitada = False
    control.acciones_externas_habilitadas = False
    control.certificacion_interna_aprobada = bool(certificacion_aprobada)
    control.certificacion_observacion = str(certificacion_observacion or "").strip() or None
    control.actualizado_por_usuario_id = getattr(usuario, "id", None); control.actualizado_por_username = getattr(usuario, "username", None)
    db_session.commit(); return control


def contrato_evento(tipo_evento, referencia_evento, datos):
    tipo = str(tipo_evento or "").strip().lower(); referencia = str(referencia_evento or "").strip()
    if tipo not in TIPOS_EVENTO: raise ValueError("El tipo de evento no es valido.")
    if not referencia: raise ValueError("La referencia idempotente es obligatoria.")
    if not isinstance(datos, dict): raise ValueError("Los datos del evento deben ser un objeto JSON.")
    return {"version_esquema": 1, "tipo": tipo, "referencia": referencia, "datos": datos}


def registrar_evento(*, control, tipo_evento, referencia_evento, datos, origen,
                     usuario=None, EventoIntegracionStaging, db_session):
    if control is None or control.modo not in {"diagnostico", "simulacion"}: raise ValueError("La cuenta no esta habilitada para pruebas internas.")
    origen = str(origen or "").strip().lower()
    if origen not in {"manual", "simulacion"}: raise ValueError("Solo se admiten eventos manuales o simulados.")
    sobre = contrato_evento(tipo_evento, referencia_evento, datos)
    existente = EventoIntegracionStaging.query.filter_by(organizacion_id=control.organizacion_id, canal=control.canal, cuenta_codigo=control.cuenta_codigo, tipo_evento=sobre["tipo"], referencia_evento=sobre["referencia"]).first()
    if existente is not None: return existente, False
    contenido = json.dumps(sobre, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    evento = EventoIntegracionStaging(
        organizacion_id=control.organizacion_id, unidad_negocio_id=control.unidad_negocio_id,
        control_id=control.id, canal=control.canal, cuenta_codigo=control.cuenta_codigo,
        tipo_evento=sobre["tipo"], referencia_evento=sobre["referencia"], origen=origen,
        estado="recibido", payload_json=contenido,
        payload_hash=hashlib.sha256(contenido.encode("utf-8")).hexdigest(),
        creado_por_usuario_id=getattr(usuario, "id", None), creado_por_username=getattr(usuario, "username", None),
    )
    db_session.add(evento); db_session.commit(); return evento, True


def procesar_evento_simulado(evento, accion, *, db_session):
    accion = str(accion or "").strip().lower()
    if evento is None: raise ValueError("El evento no existe.")
    if evento.origen not in {"manual", "simulacion"}: raise ValueError("El origen externo permanece bloqueado.")
    if accion == "validar":
        try:
            sobre = json.loads(evento.payload_json)
            contrato_evento(sobre.get("tipo"), sobre.get("referencia"), sobre.get("datos"))
            evento.estado = "validado"; evento.error_validacion = None
        except (ValueError, json.JSONDecodeError) as error:
            evento.estado = "rechazado"; evento.error_validacion = str(error)
    elif accion == "aplicar_simulado":
        if evento.estado != "validado" or evento.control.modo != "simulacion": raise ValueError("Solo un evento validado en modo simulacion puede aplicarse en staging.")
        evento.estado = "aplicado_simulado"
    elif accion == "rechazar": evento.estado = "rechazado"; evento.error_validacion = "Rechazado manualmente"
    else: raise ValueError("La accion de staging no es valida.")
    evento.fecha_proceso = ahora_utc_naive(); db_session.commit(); return evento


def matriz_preparacion(control, *, costos, reglas_economicas, reglas_canal, identidades, validaciones):
    controles = [
        ("costos_vigentes", costos > 0), ("reglas_economicas", reglas_economicas > 0),
        ("reglas_canal", reglas_canal > 0), ("identidades_publicacion", identidades > 0),
        ("validaciones_previas", validaciones > 0),
        ("certificacion_interna", bool(getattr(control, "certificacion_interna_aprobada", False))),
        ("recepcion_externa_bloqueada", not bool(getattr(control, "recepcion_externa_habilitada", False))),
        ("acciones_externas_bloqueadas", not bool(getattr(control, "acciones_externas_habilitadas", False))),
    ]
    detalle = [{"clave": clave, "cumple": cumple} for clave, cumple in controles]
    internos = detalle[:6]
    return {"detalle": detalle, "apto_pruebas_internas": all(item["cumple"] for item in internos), "conexion_real_habilitada": False, "faltantes": [item["clave"] for item in internos if not item["cumple"]]}
