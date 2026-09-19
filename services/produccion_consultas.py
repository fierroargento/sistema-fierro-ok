"""Consultas aisladas del panel preparatorio de producción."""

from services.avances_produccion import resumir_orden


def obtener_panel(organizacion_id, unidad_negocio_id, *, modelos):
    Perfil = modelos["PerfilCosteoProducto"]
    Orden = modelos["OrdenProduccion"]
    Lote = modelos["LoteProduccion"]
    perfiles = Perfil.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        tipo="produccion", activo=True,
    ).order_by(Perfil.id.asc()).all()
    ordenes = Orden.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Orden.fecha_creacion.desc()).all()
    lotes = Lote.query.filter_by(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
    ).order_by(Lote.id.desc()).all()
    return {
        "perfiles_produccion": perfiles,
        "ordenes_produccion": ordenes,
        "lotes_produccion": lotes,
        "avances_por_orden": {item.id: resumir_orden(item) for item in ordenes},
        "resumen_produccion": {
            "ordenes": len(ordenes),
            "borradores": sum(item.estado == "borrador" for item in ordenes),
            "aprobadas": sum(item.estado == "aprobada" for item in ordenes),
            "ejecuciones": sum(bool(item.ejecucion_habilitada) for item in ordenes),
        },
    }
