"""Consultas tenant del maestro de productos."""


def obtener_panel_productos_plataforma(
    Producto,
    *,
    organizacion_id,
    filtro_sku="",
    limite=100,
):
    filtro_sku = (
        filtro_sku
        or ""
    ).strip()

    consulta = Producto.query.filter_by(
        organizacion_id=organizacion_id
    )

    if filtro_sku:
        consulta = consulta.filter(
            Producto.sku.ilike(
                f"%{filtro_sku}%"
            )
        )

    productos = (
        consulta
        .order_by(
            Producto.sku.asc(),
            Producto.descripcion.asc(),
        )
        .limit(limite)
        .all()
    )

    return {
        "total_productos": (
            Producto.query.filter_by(
                organizacion_id=organizacion_id
            ).count()
        ),
        "ultimos": productos,
        "productos": productos,
        "filtro_sku": filtro_sku,
    }
