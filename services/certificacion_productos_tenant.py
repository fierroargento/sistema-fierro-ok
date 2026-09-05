"""Diagnóstico de solo lectura del límite tenant del maestro de productos."""

from sqlalchemy import func


def certificar_productos_tenant(
    organizacion_id,
    *,
    Producto,
    Catalogo,
    CatalogoProducto,
):
    """Detecta identidades ambiguas y relaciones cruzadas sin modificar datos."""
    sin_organizacion = Producto.query.filter(
        Producto.organizacion_id.is_(None)
    ).count()

    duplicados = (
        Producto.query
        .with_entities(
            func.lower(Producto.sku).label("sku"),
            func.count(Producto.id).label("cantidad"),
        )
        .filter(
            Producto.organizacion_id == organizacion_id
        )
        .group_by(func.lower(Producto.sku))
        .having(func.count(Producto.id) > 1)
        .all()
    )

    relaciones_cruzadas = (
        CatalogoProducto.query
        .join(Catalogo)
        .join(
            Producto,
            Producto.id == CatalogoProducto.producto_id,
        )
        .filter(
            Catalogo.organizacion_id == organizacion_id,
            Producto.organizacion_id != Catalogo.organizacion_id,
        )
        .count()
    )

    hallazgos = []
    if sin_organizacion:
        hallazgos.append(
            f"Hay {sin_organizacion} productos legacy sin organización."
        )
    if duplicados:
        hallazgos.append(
            f"Hay {len(duplicados)} SKU duplicados dentro del tenant."
        )
    if relaciones_cruzadas:
        hallazgos.append(
            f"Hay {relaciones_cruzadas} inclusiones vinculadas a otro tenant."
        )

    return {
        "aprobada": not hallazgos,
        "productos_tenant": Producto.query.filter_by(
            organizacion_id=organizacion_id
        ).count(),
        "productos_sin_organizacion": sin_organizacion,
        "sku_duplicados": len(duplicados),
        "relaciones_cruzadas": relaciones_cruzadas,
        "hallazgos": hallazgos,
        "integraciones_habilitables": False,
        "motivo_integraciones": (
            "Los pedidos operativos todavía no tienen tenant obligatorio."
        ),
    }
