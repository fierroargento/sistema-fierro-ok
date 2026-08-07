"""Contexto obligatorio de unidad para administración comercial."""


class UnidadNegocioError(ValueError):
    pass


def resolver_unidad_activa(organizacion_id, unidad_sesion, *, UnidadNegocio):
    unidades = UnidadNegocio.query.filter_by(
        organizacion_id=organizacion_id, activa=True,
    ).order_by(UnidadNegocio.nombre).all()
    if not unidades:
        raise UnidadNegocioError("La organización no tiene unidades de negocio activas.")
    ids = {unidad.id for unidad in unidades}
    try:
        solicitada = int(unidad_sesion) if unidad_sesion is not None else None
    except (TypeError, ValueError):
        solicitada = None
    unidad = next((item for item in unidades if item.id == solicitada), unidades[0])
    return unidad, unidades


def validar_unidad(registro, unidad_id, nombre="El registro"):
    if registro is None or registro.unidad_negocio_id != unidad_id:
        raise UnidadNegocioError(f"{nombre} no pertenece a la unidad activa.")
    return registro
