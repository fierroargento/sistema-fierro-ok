"""Lectura del historial existente de precios por organización, unidad y lista."""


def obtener_historial_precio(organizacion_id, unidad_negocio_id, lista_id, inclusion_id, *, Observacion):
    return Observacion.query.filter_by(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        lista_precio_id=lista_id,
        catalogo_producto_id=inclusion_id,
        tipo="precio",
    ).order_by(Observacion.fecha_observacion.desc(), Observacion.id.desc()).all()
