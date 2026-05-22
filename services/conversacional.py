from datetime import datetime, UTC


def obtener_estado_conversacional_service(
    pedido,
    EstadoConversacionalPedido,
    db,
    crear_si_no_existe=True,
):
    """
    Devuelve el estado conversacional APB asociado al pedido.

    Si no existe y crear_si_no_existe=True,
    lo crea con valores seguros.
    """

    if not pedido:
        return None

    estado = EstadoConversacionalPedido.query.filter_by(
        pedido_id=pedido.id
    ).first()

    if estado or not crear_si_no_existe:
        return estado

    estado = EstadoConversacionalPedido(
        pedido_id=pedido.id,
        owner_actual="bot",
        estado_conversacional="recolectando_datos",
        canal_activo="ml",
        flujo_base="",
        takeover_activo=False,
        bot_pausado=False,
        cross_sell_activo=False,
        ultima_interaccion=datetime.now(UTC),
    )

    db.session.add(estado)
    db.session.commit()

    return estado


def actualizar_estado_conversacional_service(
    pedido,
    EstadoConversacionalPedido,
    db,
    owner_actual=None,
    estado_conversacional=None,
    canal_activo=None,
    flujo_base=None,
    takeover_activo=None,
    bot_pausado=None,
    cross_sell_activo=None,
    ultimo_mensaje_cliente=None,
    ultimo_mensaje_bot=None,
):
    """
    Actualiza el estado conversacional APB
    sin modificar el flujo operativo.
    """

    estado = obtener_estado_conversacional_service(
        pedido,
        EstadoConversacionalPedido,
        db,
    )

    if not estado:
        return None

    if owner_actual is not None:
        estado.owner_actual = owner_actual

    if estado_conversacional is not None:
        estado.estado_conversacional = estado_conversacional

    if canal_activo is not None:
        estado.canal_activo = canal_activo

    if flujo_base is not None:
        estado.flujo_base = flujo_base

    if takeover_activo is not None:
        estado.takeover_activo = bool(takeover_activo)

    if bot_pausado is not None:
        estado.bot_pausado = bool(bot_pausado)

    if cross_sell_activo is not None:
        estado.cross_sell_activo = bool(cross_sell_activo)

    if ultimo_mensaje_cliente is not None:
        estado.ultimo_mensaje_cliente = ultimo_mensaje_cliente

    if ultimo_mensaje_bot is not None:
        estado.ultimo_mensaje_bot = ultimo_mensaje_bot

    estado.ultima_interaccion = datetime.now(UTC)

    db.session.commit()

    return estado