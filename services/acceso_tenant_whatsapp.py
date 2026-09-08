"""Frontera obligatoria para leer mensajes WhatsApp dentro de un tenant."""


def _id_positivo(valor, nombre):
    try:
        resultado = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Falta una identidad válida de {nombre}.") from error
    if resultado <= 0:
        raise ValueError(f"Falta una identidad válida de {nombre}.")
    return resultado


def consulta_whatsapp_tenant(
    WhatsAppMensaje, organizacion_id, unidad_negocio_id=None,
):
    """Consulta mensajes por organización y, opcionalmente, por unidad."""
    organizacion_id = _id_positivo(organizacion_id, "organización")
    consulta = WhatsAppMensaje.query.filter_by(
        organizacion_id=organizacion_id,
    )
    if unidad_negocio_id is not None:
        consulta = consulta.filter_by(
            unidad_negocio_id=_id_positivo(
                unidad_negocio_id, "unidad de negocio",
            ),
        )
    return consulta


def obtener_mensaje_whatsapp_tenant(
    mensaje_id, organizacion_id, *, WhatsAppMensaje,
    unidad_negocio_id=None,
):
    """Obtiene un mensaje sin permitir una búsqueda global por ID."""
    mensaje_id = _id_positivo(mensaje_id, "mensaje")
    return consulta_whatsapp_tenant(
        WhatsAppMensaje,
        organizacion_id,
        unidad_negocio_id,
    ).filter_by(id=mensaje_id).first()


def validar_mensaje_whatsapp_en_tenant(
    mensaje, organizacion_id, unidad_negocio_id=None,
):
    """Valida un mensaje ya cargado antes de exponerlo o modificarlo."""
    esperado = _id_positivo(organizacion_id, "organización")
    actual = getattr(mensaje, "organizacion_id", None)
    if actual is None or int(actual) != esperado:
        raise ValueError("El mensaje no pertenece a la organización activa.")
    if unidad_negocio_id is not None:
        unidad = _id_positivo(unidad_negocio_id, "unidad de negocio")
        if getattr(mensaje, "unidad_negocio_id", None) != unidad:
            raise ValueError(
                "El mensaje no pertenece a la unidad de negocio activa."
            )
    return mensaje
