"""
Operaciones sobre el maestro de productos de una organización.
"""


from services.productos_catalogo import (
    producto_desde_form_catalogo,
    validar_producto_catalogo,
)
from services.productos_catalogo_db import (
    crear_y_guardar_producto_catalogo,
    eliminar_producto_catalogo,
    guardar_producto_catalogo,
)


def _producto_por_id(
    Producto,
    producto_id,
    nombre,
    *,
    organizacion_id,
):
    try:
        producto_id = int(producto_id)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{nombre} no es válido."
        ) from error

    producto = Producto.query.filter_by(
        id=producto_id,
        organizacion_id=organizacion_id,
    ).first()

    if producto is None:
        raise ValueError(
            f"No se encontró {nombre}."
        )

    return producto


def _validar_sku_disponible(
    Producto,
    sku,
    *,
    organizacion_id,
    producto_actual=None,
):
    if not sku:
        return

    existente = (
        Producto.query
        .filter(
            Producto.organizacion_id
            == organizacion_id,
            Producto.sku.ilike(sku)
        )
        .first()
    )

    if (
        existente is not None
        and (
            producto_actual is None
            or existente.id
            != producto_actual.id
        )
    ):
        raise ValueError(
            "Ya existe otro producto "
            "con ese SKU."
        )


def procesar_accion_productos_plataforma(
    accion,
    formulario,
    archivos,
    *,
    Producto,
    db,
    sincronizar_excel,
    organizacion_id,
):
    if accion == "importar_excel":
        archivo = archivos.get(
            "archivo_productos"
        )

        if (
            archivo is None
            or not archivo.filename
        ):
            raise ValueError(
                "Tenés que seleccionar un Excel."
            )

        cantidad = sincronizar_excel(
            archivo,
            organizacion_id=organizacion_id,
        )

        return (
            f"Productos actualizados: {cantidad}",
            "",
        )

    if accion == "crear_producto":
        datos = producto_desde_form_catalogo(
            formulario
        )
        errores = validar_producto_catalogo(
            datos
        )

        if errores:
            raise ValueError(
                " ".join(errores)
            )

        _validar_sku_disponible(
            Producto,
            datos.get("sku"),
            organizacion_id=organizacion_id,
        )

        crear_y_guardar_producto_catalogo(
            Producto,
            datos,
            db=db,
            organizacion_id=organizacion_id,
        )

        return (
            "Producto creado correctamente.",
            datos.get("sku") or "",
        )

    if accion == "editar_producto":
        producto = _producto_por_id(
            Producto,
            formulario.get("producto_id"),
            "el producto a editar",
            organizacion_id=organizacion_id,
        )
        datos = producto_desde_form_catalogo(
            formulario
        )
        errores = validar_producto_catalogo(
            datos
        )

        if errores:
            raise ValueError(
                " ".join(errores)
            )

        _validar_sku_disponible(
            Producto,
            datos.get("sku"),
            organizacion_id=organizacion_id,
            producto_actual=producto,
        )

        guardar_producto_catalogo(
            producto,
            datos,
            db=db,
        )

        return (
            "Producto actualizado correctamente.",
            datos.get("sku") or "",
        )

    if accion == "eliminar_producto":
        producto = _producto_por_id(
            Producto,
            formulario.get("producto_id"),
            "el producto a eliminar",
            organizacion_id=organizacion_id,
        )
        sku = producto.sku or ""

        eliminar_producto_catalogo(
            producto,
            db,
        )

        return (
            (
                f"Producto {sku} eliminado "
                "correctamente."
            ),
            "",
        )

    raise ValueError(
        "La acción no es válida."
    )
