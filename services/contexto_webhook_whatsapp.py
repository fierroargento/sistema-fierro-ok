"""Resolución pura y desconectada del tenant de un evento WhatsApp."""


class ContextoWebhookWhatsAppError(ValueError):
    pass


def extraer_phone_number_id(payload):
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return ""
    return str((value.get("metadata") or {}).get("phone_number_id") or "").strip()


def resolver_contexto_webhook_whatsapp(payload, vinculos):
    """Devuelve organización/unidad sólo ante una coincidencia activa inequívoca.

    ``vinculos`` admite objetos o diccionarios. No consulta red ni base de datos.
    """
    phone_number_id = extraer_phone_number_id(payload)
    if not phone_number_id:
        raise ContextoWebhookWhatsAppError(
            "El evento no informa phone_number_id."
        )

    def valor(vinculo, nombre, default=None):
        if isinstance(vinculo, dict):
            return vinculo.get(nombre, default)
        return getattr(vinculo, nombre, default)

    candidatos = [
        vinculo for vinculo in (vinculos or [])
        if str(valor(vinculo, "phone_number_id", "") or "").strip()
        == phone_number_id
        and str(valor(vinculo, "estado", "") or "").lower() == "activo"
    ]
    if len(candidatos) != 1:
        motivo = "sin vínculo activo" if not candidatos else "vínculo ambiguo"
        raise ContextoWebhookWhatsAppError(
            f"phone_number_id {motivo}; el evento no puede procesarse."
        )

    vinculo = candidatos[0]
    try:
        organizacion_id = int(valor(vinculo, "organizacion_id"))
        unidad_negocio_id = int(valor(vinculo, "unidad_negocio_id"))
    except (TypeError, ValueError) as error:
        raise ContextoWebhookWhatsAppError(
            "El vínculo no tiene identidad tenant válida."
        ) from error
    if organizacion_id <= 0 or unidad_negocio_id <= 0:
        raise ContextoWebhookWhatsAppError(
            "El vínculo no tiene identidad tenant válida."
        )
    return {
        "phone_number_id": phone_number_id,
        "organizacion_id": organizacion_id,
        "unidad_negocio_id": unidad_negocio_id,
    }
