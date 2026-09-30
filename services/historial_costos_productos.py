"""Lectura de versiones históricas existentes, restringida a organización y unidad."""


def obtener_historial_costo_producto(organizacion_id, unidad_negocio_id, producto_id, *, Costo):
    return Costo.query.filter_by(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        producto_id=producto_id,
    ).order_by(Costo.numero_version.desc()).all()
