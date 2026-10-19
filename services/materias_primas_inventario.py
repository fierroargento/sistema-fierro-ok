"""Identidad de insumos inventariables usando el maestro de SKU existente."""

import json
import re

from services.unidades_materias_primas import definir_unidad, leer_unidad_item


def identidad_insumo(item):
    if item is None or item.tipo != "insumo":
        return None
    try:
        datos = json.loads(item.atributos_json or "{}")
        return int(datos["insumo_productivo_id"])
    except (ValueError, TypeError, KeyError):
        return None


def validar_insumo(insumo, organizacion_id, unidad_negocio_id):
    if insumo is None or int(insumo.organizacion_id) != int(organizacion_id):
        raise ValueError("El insumo no pertenece a la organización activa.")
    if insumo.unidad_negocio_id not in (None, unidad_negocio_id):
        raise ValueError("El insumo no pertenece a la unidad activa.")
    if not insumo.activo or insumo.tipo == "servicio_productivo":
        raise ValueError("Seleccioná un insumo físico activo.")


def preparar_materia_prima(*, insumo, sku, organizacion_id, unidad_negocio_id,
                          Producto, ItemInventario, db_session, precision_inventario="unidad"):
    """Crea identidad interna inactiva, sin catálogo comercial ni existencias."""
    validar_insumo(insumo, organizacion_id, unidad_negocio_id)
    unidad = definir_unidad(insumo.unidad_medida, precision_inventario)
    sku = str(sku or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,79}", sku):
        raise ValueError("El SKU debe tener hasta 80 letras, números, puntos, guiones o guiones bajos.")
    # Bloquea preparaciones simultáneas del mismo insumo.
    db_session.query(type(insumo)).filter_by(id=insumo.id).with_for_update().one()
    items = ItemInventario.query.filter_by(organizacion_id=organizacion_id).all()
    anteriores = [item for item in items if identidad_insumo(item) == insumo.id]
    if anteriores:
        if len(anteriores) == 1 and anteriores[0].sku == sku:
            anterior = leer_unidad_item(anteriores[0])
            if anterior['factor_inventario'] != unidad['factor_inventario'] or anterior['unidad_medida'] != unidad['unidad_medida']:
                raise ValueError('El SKU existente conserva su unidad y precisión. No se reinterpretan sus saldos ni su historial.')
            return anteriores[0], False
        raise ValueError("El insumo ya tiene un SKU preparado. Usá el existente.")
    if any(item.sku.upper() == sku for item in items):
        raise ValueError("El SKU ya pertenece a otro ítem de inventario.")
    producto = Producto.query.filter_by(organizacion_id=organizacion_id, sku=sku).first()
    if producto is not None:
        raise ValueError("El SKU ya existe en el maestro de productos; elegí uno exclusivo para el insumo.")
    # ItemInventario requiere producto_id. Esta identidad física no se incluye
    # en ningún catálogo comercial ni habilita transportes o publicaciones.
    producto = Producto(organizacion_id=organizacion_id, sku=sku,
                        descripcion=insumo.nombre, permite_correo=False,
                        permite_via_cargo=False, requiere_revision_logistica=True)
    db_session.add(producto)
    db_session.flush()
    item = ItemInventario(
        organizacion_id=organizacion_id, producto_id=producto.id,
        catalogo_producto_id=None, sku=sku, nombre=insumo.nombre,
        tipo="insumo", activo=False,
        atributos_json=json.dumps({"insumo_productivo_id": insumo.id,
                                   **unidad}, sort_keys=True),
    )
    db_session.add(item)
    db_session.commit()
    return item, True


def validar_existencia_insumo(insumo, existencia, organizacion_id, unidad_negocio_id):
    validar_insumo(insumo, organizacion_id, unidad_negocio_id)
    if existencia is None or int(existencia.organizacion_id) != int(organizacion_id):
        raise ValueError("La existencia no pertenece a la organización activa.")
    item = existencia.item_inventario
    if (item is None or int(item.organizacion_id) != int(organizacion_id)
            or identidad_insumo(item) != insumo.id
            or int(item.producto_id) != int(existencia.producto_id)):
        raise ValueError("La existencia debe corresponder al SKU preparado para este insumo.")
    if (not item.activo or not existencia.control_activo
            or not existencia.sucursal.activa
            or int(existencia.sucursal.organizacion_id) != int(organizacion_id)):
        raise ValueError("Activá el SKU, la ubicación y el control de la existencia antes de mapear.")
    unidad = leer_unidad_item(item)
    if str(insumo.unidad_medida).strip().casefold() != unidad['unidad_medida'].casefold():
        raise ValueError('La unidad del insumo cambió después de preparar el SKU; revisala antes de mapear.')
