"""Selección persistente de destino preparatorio, aislada por contexto y orden."""


def clave_destino(organizacion_id, unidad_negocio_id, orden_id):
    return f"produccion:destino:{int(organizacion_id)}:{int(unidad_negocio_id)}:{int(orden_id)}"


def validar_destino(orden, existencia, organizacion_id, unidad_negocio_id):
    if (int(orden.organizacion_id) != int(organizacion_id)
            or int(orden.unidad_negocio_id) != int(unidad_negocio_id)):
        raise ValueError("La orden no pertenece al contexto activo.")
    if (existencia is None or int(existencia.organizacion_id) != int(organizacion_id)
            or int(existencia.producto_id) != int(orden.producto_id)):
        raise ValueError("El destino no corresponde al producto de la orden y organización activa.")
    item = existencia.item_inventario
    sucursal = existencia.sucursal
    if (not existencia.control_activo or item is None or not item.activo
            or item.tipo != "producto" or int(item.organizacion_id) != int(organizacion_id)
            or int(item.producto_id) != int(orden.producto_id)
            or sucursal is None or not sucursal.activa
            or int(sucursal.organizacion_id) != int(organizacion_id)):
        raise ValueError("El destino necesita ubicación, SKU principal y control activos.")


def leer_destino(*, orden, organizacion_id, unidad_negocio_id, ConfiguracionSistema):
    dato = ConfiguracionSistema.query.filter_by(
        clave=clave_destino(organizacion_id, unidad_negocio_id, orden.id),
    ).first()
    if dato is None:
        return None
    try:
        return int(dato.valor)
    except (ValueError, TypeError):
        return -1  # Una configuración dañada bloquea; nunca elige otro depósito.


def guardar_destino(*, orden, existencia, organizacion_id, unidad_negocio_id,
                    ConfiguracionSistema, db_session):
    db_session.query(type(orden)).filter_by(id=orden.id).with_for_update().populate_existing().one()
    validar_destino(orden, existencia, organizacion_id, unidad_negocio_id)
    if orden.estado in ("cerrada", "cancelada"):
        raise ValueError("No se puede cambiar el destino de una orden cerrada o cancelada.")
    clave = clave_destino(organizacion_id, unidad_negocio_id, orden.id)
    dato = ConfiguracionSistema.query.filter_by(clave=clave).first()
    if dato is None:
        dato = ConfiguracionSistema(clave=clave)
        db_session.add(dato)
    dato.valor = str(existencia.id)
    dato.descripcion = "Destino preparatorio de producción; sin movimientos de inventario."
    db_session.commit()
