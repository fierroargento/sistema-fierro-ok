"""Frontera obligatoria para leer pedidos dentro de un tenant."""


def _id_positivo(valor, nombre):
    try:
        resultado = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Falta una identidad válida de {nombre}.") from error
    if resultado <= 0:
        raise ValueError(f"Falta una identidad válida de {nombre}.")
    return resultado


def consulta_pedidos_tenant(Pedido, organizacion_id, unidad_negocio_id=None):
    """Devuelve una consulta siempre limitada por organización y, opcionalmente, unidad."""
    organizacion_id = _id_positivo(organizacion_id, "organización")
    consulta = Pedido.query.filter_by(organizacion_id=organizacion_id)
    if unidad_negocio_id is not None:
        consulta = consulta.filter_by(
            unidad_negocio_id=_id_positivo(unidad_negocio_id, "unidad de negocio")
        )
    return consulta


def obtener_pedido_tenant(
    pedido_id, organizacion_id, *, Pedido, unidad_negocio_id=None,
):
    """Obtiene un pedido sin permitir búsquedas globales por ID."""
    pedido_id = _id_positivo(pedido_id, "pedido")
    return consulta_pedidos_tenant(
        Pedido, organizacion_id, unidad_negocio_id,
    ).filter_by(id=pedido_id).first()


def validar_pedido_en_tenant(pedido, organizacion_id, unidad_negocio_id=None):
    """Valida un objeto ya cargado antes de exponerlo o modificarlo."""
    esperado = _id_positivo(organizacion_id, "organización")
    actual = getattr(pedido, "organizacion_id", None)
    if actual is None or int(actual) != esperado:
        raise ValueError("El pedido no pertenece a la organización activa.")
    if unidad_negocio_id is not None:
        unidad = _id_positivo(unidad_negocio_id, "unidad de negocio")
        if getattr(pedido, "unidad_negocio_id", None) != unidad:
            raise ValueError("El pedido no pertenece a la unidad de negocio activa.")
    return pedido
