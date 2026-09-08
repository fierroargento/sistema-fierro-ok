"""Normaliza eventos WhatsApp simulados sin red, base ni efectos externos."""

import hashlib
import json

from services.contexto_webhook_whatsapp import resolver_contexto_webhook_whatsapp


TIPO_MENSAJE = "mensaje_entrante"
TIPO_ESTADO = "estado_mensaje"


def _huella(datos):
    canonico = json.dumps(
        datos, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _texto_mensaje(mensaje):
    tipo = str(mensaje.get("type") or "").strip().lower()
    if tipo == "text":
        return str((mensaje.get("text") or {}).get("body") or "").strip()
    if tipo == "interactive":
        interactivo = mensaje.get("interactive") or {}
        respuesta = (
            interactivo.get("button_reply")
            or interactivo.get("list_reply")
            or {}
        )
        return str(respuesta.get("title") or "").strip()
    return ""


def _sobre(contexto, tipo, referencia, datos):
    contenido = {
        "version_esquema": 1,
        "canal": "whatsapp",
        "cuenta_codigo": contexto["phone_number_id"],
        "organizacion_id": contexto["organizacion_id"],
        "unidad_negocio_id": contexto["unidad_negocio_id"],
        "tipo": tipo,
        "referencia": referencia,
        "datos": datos,
    }
    return {**contenido, "payload_hash": _huella(contenido)}


def procesar_payload_whatsapp_offline(payload, vinculos, referencias_vistas=None):
    """Procesa un fixture Meta y devuelve sobres, duplicados y errores aislados."""
    if not isinstance(payload, dict):
        raise ValueError("El fixture WhatsApp debe ser un objeto JSON.")
    vistas = set(str(item) for item in (referencias_vistas or set()))
    sobres = []
    duplicados = []
    errores = []

    for numero_entry, entry in enumerate(payload.get("entry") or [], start=1):
        for numero_cambio, cambio in enumerate(entry.get("changes") or [], start=1):
            fragmento = {"entry": [{"changes": [cambio]}]}
            ubicacion = f"entry {numero_entry}, cambio {numero_cambio}"
            try:
                contexto = resolver_contexto_webhook_whatsapp(fragmento, vinculos)
                value = cambio.get("value") or {}
                candidatos = []
                for mensaje in value.get("messages") or []:
                    message_id = str(mensaje.get("id") or "").strip()
                    telefono = str(mensaje.get("from") or "").strip()
                    if not message_id or not telefono:
                        raise ValueError("El mensaje no tiene id o remitente.")
                    candidatos.append(_sobre(
                        contexto, TIPO_MENSAJE, f"{message_id}:in",
                        {
                            "message_id_meta": message_id,
                            "telefono": telefono,
                            "tipo_mensaje": str(mensaje.get("type") or ""),
                            "texto": _texto_mensaje(mensaje),
                            "timestamp": mensaje.get("timestamp"),
                        },
                    ))
                for estado in value.get("statuses") or []:
                    message_id = str(estado.get("id") or "").strip()
                    nombre = str(estado.get("status") or "").strip().lower()
                    if not message_id or not nombre:
                        raise ValueError("El estado no tiene id o status.")
                    candidatos.append(_sobre(
                        contexto, TIPO_ESTADO,
                        f"{message_id}:{nombre}",
                        {
                            "message_id_meta": message_id,
                            "estado_meta": nombre,
                            "timestamp": estado.get("timestamp"),
                            "errores": estado.get("errors") or [],
                        },
                    ))
                for sobre in candidatos:
                    clave = sobre["referencia"]
                    if clave in vistas:
                        duplicados.append(clave)
                    else:
                        vistas.add(clave)
                        sobres.append(sobre)
            except (ValueError, TypeError) as error:
                errores.append({"ubicacion": ubicacion, "error": str(error)})

    return {
        "sobres": sobres,
        "duplicados": duplicados,
        "errores": errores,
        "resumen": {
            "procesados": len(sobres),
            "duplicados": len(duplicados),
            "errores": len(errores),
        },
        "escrituras": 0,
        "acciones_externas": 0,
    }


def procesar_documento_whatsapp_offline(contenido, vinculos, referencias_vistas=None):
    if isinstance(contenido, bytes):
        contenido = contenido.decode("utf-8-sig")
    try:
        payload = json.loads(contenido)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("El fixture no contiene JSON UTF-8 valido.") from error
    return procesar_payload_whatsapp_offline(payload, vinculos, referencias_vistas)
