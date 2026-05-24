def actualizar_estado_conversacional_wa(
    pedido,
    **kwargs,
):
    from app import actualizar_estado_conversacional

    return actualizar_estado_conversacional(
        pedido,
        **kwargs,
    )


def registrar_evento_operativo_wa(
    **kwargs,
):
    from app import registrar_evento_operativo

    return registrar_evento_operativo(
        **kwargs,
    )