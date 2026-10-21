"""Consultas tenant del maestro de productos."""


def obtener_panel_productos_plataforma(
    Producto,
    *,
    organizacion_id,
    filtro_sku="",
    limite=100,
    pagina=1,
):
    filtro_sku = (
        filtro_sku
        or ""
    ).strip()

    consulta = Producto.query.filter_by(
        organizacion_id=organizacion_id
    )

    if filtro_sku:
        from sqlalchemy import or_
        from services.producto_habilitaciones import esquema_ficha_disponible
        patron = f"%{filtro_sku}%"
        criterios = [Producto.sku.ilike(patron), Producto.descripcion.ilike(patron)]
        if esquema_ficha_disponible(consulta.session):
            from models.producto_ficha_maestra import ProductoFichaMaestra
            consulta = consulta.outerjoin(ProductoFichaMaestra,
                (ProductoFichaMaestra.producto_id == Producto.id)
                & (ProductoFichaMaestra.organizacion_id == organizacion_id))
            criterios.extend([ProductoFichaMaestra.nombre.ilike(patron), ProductoFichaMaestra.linea.ilike(patron)])
        from services.productos_datos_generales import esquema_datos_disponible
        if esquema_datos_disponible(consulta.session):
            from models.producto_datos_generales import ProductoDatosGenerales, ProductoProveedor, ProductoCodigoBarras
            consulta = consulta.outerjoin(ProductoDatosGenerales,
                (ProductoDatosGenerales.producto_id == Producto.id) & (ProductoDatosGenerales.organizacion_id == organizacion_id))
            criterios.extend([ProductoDatosGenerales.marca.ilike(patron), ProductoDatosGenerales.rubro.ilike(patron), ProductoDatosGenerales.subrubro.ilike(patron)])
            criterios.extend([
                consulta.session.query(ProductoProveedor.id).filter(ProductoProveedor.organizacion_id == organizacion_id,
                    ProductoProveedor.producto_id == Producto.id, ProductoProveedor.codigo.ilike(patron)).exists(),
                consulta.session.query(ProductoCodigoBarras.id).filter(ProductoCodigoBarras.organizacion_id == organizacion_id,
                    ProductoCodigoBarras.producto_id == Producto.id, ProductoCodigoBarras.codigo.ilike(patron)).exists(),
            ])
        consulta = consulta.filter(or_(*criterios))

    total_resultados = consulta.count()
    total_paginas = max(1, (total_resultados + limite - 1) // limite)
    try:
        pagina = max(1, min(int(pagina), total_paginas))
    except (ValueError, TypeError):
        pagina = 1

    productos = (
        consulta
        .order_by(
            Producto.sku.asc(),
            Producto.descripcion.asc(),
        )
        .offset((pagina - 1) * limite)
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
        "pagina": pagina,
        "por_pagina": limite,
        "total_paginas": total_paginas,
        "total_resultados": total_resultados,
        "desde": (pagina - 1) * limite + 1 if total_resultados else 0,
        "hasta": (pagina - 1) * limite + len(productos),
    }
