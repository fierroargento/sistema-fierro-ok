"""Consultas tenant del panel de compras."""


def obtener_panel_compras(organizacion_id, unidad_negocio_id, *, modelos):
    Proveedor = modelos["ProveedorCompra"]
    Orden = modelos["OrdenCompra"]
    Recepcion = modelos["RecepcionCompra"]
    Insumo = modelos["InsumoProductivo"]
    proveedores = Proveedor.query.filter_by(
        organizacion_id=organizacion_id,
    ).order_by(Proveedor.razon_social.asc()).all()
    ordenes = Orden.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Orden.fecha_creacion.desc()).all()
    recepciones = Recepcion.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Recepcion.fecha_creacion.desc()).all()
    insumos = Insumo.query.filter_by(
        organizacion_id=organizacion_id, activo=True,
    ).order_by(Insumo.nombre.asc()).all()
    return {
        "proveedores": proveedores,
        "ordenes_compra": ordenes,
        "recepciones_compra": recepciones,
        "insumos_compra": insumos,
        "resumen_compras": {
            "proveedores_activos": sum(item.estado == "activo" for item in proveedores),
            "ordenes_abiertas": sum(item.estado in {"borrador", "en_revision", "aprobada"} for item in ordenes),
            "ordenes_aprobadas": sum(item.estado == "aprobada" for item in ordenes),
            "recepciones_preparatorias": sum(item.estado == "preparatoria" for item in recepciones),
        },
    }
