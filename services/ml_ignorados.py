from datetime import datetime, UTC


def ml_pedido_esta_ignorado_service(
    order_id,
    PedidoIgnoradoML,
):
    order_id = str(order_id or "").strip()

    if not order_id:
        return False

    try:
        return (
            PedidoIgnoradoML.query
            .filter_by(id_venta=order_id)
            .first()
            is not None
        )

    except Exception:
        return False


def ml_registrar_pedido_ignorado_service(
    pedido,
    motivo,
    PedidoIgnoradoML,
    db,
    usuario="sistema",
):
    if (
        not pedido
        or pedido.canal != "Mercado Libre"
        or not pedido.id_venta
    ):
        return None

    order_id = str(
        pedido.id_venta or ""
    ).strip()

    if not order_id:
        return None

    ignorado = (
        PedidoIgnoradoML.query
        .filter_by(id_venta=order_id)
        .first()
    )

    if not ignorado:
        ignorado = PedidoIgnoradoML(
            id_venta=order_id
        )

        db.session.add(ignorado)

    ignorado.motivo = motivo
    ignorado.pedido_local_id = pedido.id
    ignorado.usuario = usuario or "sistema"
    ignorado.fecha = datetime.now(UTC)

    return ignorado


def ml_registrar_order_ignorado_service(
    order_id,
    motivo,
    PedidoIgnoradoML,
    db,
    usuario="sistema",
):
    """
    Registra una orden ML omitida aunque no exista Pedido local.

    APB:
    se usa para ventas históricas ya entregadas,
    evitando que vuelvan a importarse.
    """

    order_id = str(order_id or "").strip()

    if not order_id:
        return None

    ignorado = (
        PedidoIgnoradoML.query
        .filter_by(id_venta=order_id)
        .first()
    )

    if not ignorado:
        ignorado = PedidoIgnoradoML(
            id_venta=order_id
        )

        db.session.add(ignorado)

    ignorado.motivo = motivo
    ignorado.pedido_local_id = None
    ignorado.usuario = usuario or "sistema"
    ignorado.fecha = datetime.now(UTC)

    return ignorado