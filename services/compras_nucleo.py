"""Operaciones internas de compras; las recepciones no impactan stock ni costos."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _texto(valor, nombre, maximo):
    texto = str(valor or "").strip()
    if not texto:
        raise ValueError(f"{nombre} es obligatorio.")
    if len(texto) > maximo:
        raise ValueError(f"{nombre} supera {maximo} caracteres.")
    return texto


def _cantidad(valor):
    try:
        numero = Decimal(str(valor or "").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("La cantidad no es válida.") from error
    if not numero.is_finite() or numero <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    return numero.quantize(Decimal("0.000001"))


def _centavos(valor):
    try:
        numero = Decimal(str(valor or "").replace(".", "").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("El precio unitario no es válido.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError("El precio unitario no puede ser negativo.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def crear_proveedor(datos, *, organizacion_id, ProveedorCompra, db_session):
    proveedor = ProveedorCompra(
        organizacion_id=organizacion_id,
        codigo=_texto(datos.get("codigo"), "El código", 80).upper(),
        razon_social=_texto(datos.get("razon_social"), "La razón social", 200),
        cuit=str(datos.get("cuit") or "").strip() or None,
        email=str(datos.get("email") or "").strip() or None,
        telefono=str(datos.get("telefono") or "").strip() or None,
        observacion=str(datos.get("observacion") or "").strip() or None,
    )
    db_session.add(proveedor)
    db_session.commit()
    return proveedor


def crear_orden(datos, *, organizacion_id, unidad_negocio_id, proveedor,
                insumo, OrdenCompra, OrdenCompraItem, db_session, usuario_id=None):
    if int(proveedor.organizacion_id) != int(organizacion_id) or proveedor.estado != "activo":
        raise ValueError("El proveedor no pertenece al tenant activo o está inactivo.")
    if insumo is not None and int(insumo.organizacion_id) != int(organizacion_id):
        raise ValueError("El insumo no pertenece al tenant activo.")
    cantidad = _cantidad(datos.get("cantidad"))
    precio = _centavos(datos.get("precio_unitario"))
    subtotal = int((cantidad * Decimal(precio)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    orden = OrdenCompra(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        proveedor_id=proveedor.id,
        numero=_texto(datos.get("numero"), "El número", 80).upper(),
        estado="borrador", total_centavos=subtotal,
        observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    orden.items.append(OrdenCompraItem(
        insumo_id=getattr(insumo, "id", None),
        descripcion=_texto(datos.get("descripcion"), "La descripción", 250),
        unidad_medida=_texto(datos.get("unidad_medida"), "La unidad", 30),
        cantidad=cantidad, precio_unitario_centavos=precio,
        subtotal_centavos=subtotal,
    ))
    db_session.add(orden)
    db_session.commit()
    return orden


def cambiar_estado_orden(orden, estado, *, organizacion_id, db_session):
    if int(orden.organizacion_id) != int(organizacion_id):
        raise ValueError("La orden no pertenece al tenant activo.")
    permitidas = {
        "borrador": {"en_revision", "cancelada"},
        "en_revision": {"aprobada", "borrador", "cancelada"},
        "aprobada": {"cerrada", "cancelada"},
        "cerrada": set(), "cancelada": set(),
    }
    if estado not in permitidas.get(orden.estado, set()):
        raise ValueError("La transición de estado no está permitida.")
    orden.estado = estado
    db_session.commit()
    return orden


def preparar_recepcion(datos, *, orden, organizacion_id, unidad_negocio_id,
                       RecepcionCompra, RecepcionCompraItem, db_session, usuario_id=None):
    if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La orden no pertenece al tenant y unidad activos.")
    if orden.estado != "aprobada":
        raise ValueError("Solo una orden aprobada admite una recepción preparatoria.")
    if any(item.estado != "anulada" for item in getattr(orden, "recepciones", ())):
        raise ValueError("La orden ya tiene una recepción preparatoria vigente.")
    recepcion = RecepcionCompra(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        orden_compra_id=orden.id,
        numero=_texto(datos.get("numero"), "El número de recepción", 80).upper(),
        estado="preparatoria", impacta_stock=False, impacta_costos=False,
        comprobante_referencia=str(datos.get("comprobante_referencia") or "").strip() or None,
        observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    for item in orden.items:
        recepcion.items.append(RecepcionCompraItem(
            orden_compra_item_id=item.id,
            cantidad_recibida=item.cantidad,
        ))
    db_session.add(recepcion)
    db_session.commit()
    return recepcion
