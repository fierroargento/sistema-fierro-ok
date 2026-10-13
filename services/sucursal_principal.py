"""Selección de una única sucursal principal dentro de la organización."""


def establecer_sucursal_principal(
    *, organizacion_id, sucursal_id, confirmacion,
    modelo_organizacion, modelo_sucursal, sesion,
):
    if confirmacion != "1":
        raise ValueError("Confirmá el cambio de sucursal principal.")
    try:
        # Serializar las selecciones simultáneas de la misma organización.
        organizacion = sesion.query(modelo_organizacion).filter(
            modelo_organizacion.id == organizacion_id
        ).with_for_update().one_or_none()
        if organizacion is None:
            raise ValueError("No se encontró la organización activa.")
        sucursales = sesion.query(modelo_sucursal).filter(
            modelo_sucursal.organizacion_id == organizacion_id
        ).order_by(modelo_sucursal.id.asc()).with_for_update().all()
        seleccionada = next(
            (sucursal for sucursal in sucursales if sucursal.id == sucursal_id),
            None,
        )
        if seleccionada is None:
            raise ValueError("La sucursal no pertenece al tenant activo.")
        if not seleccionada.activa:
            raise ValueError("La sucursal principal debe estar activa.")
        for sucursal in sucursales:
            sucursal.es_principal = sucursal.id == sucursal_id
        sesion.commit()
        return f"Sucursal principal actualizada: {seleccionada.codigo} — {seleccionada.nombre}."
    except Exception:
        sesion.rollback()
        raise
