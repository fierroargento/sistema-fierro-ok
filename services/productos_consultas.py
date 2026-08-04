"""
Consultas del maestro global de productos.
"""


def obtener_panel_productos_plataforma(
    Producto,
    *,
    filtro_sku="",
    limite=100,
):
    filtro_sku = (
        filtro_sku
        or ""
    ).strip()

    consulta = Producto.query

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
            Producto.query.count()
        ),
        "ultimos": productos,
        "productos": productos,
        "filtro_sku": filtro_sku,
    }
