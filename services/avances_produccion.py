"""Registro interno de avances sin efectos físicos o contables."""

from decimal import Decimal, InvalidOperation


def _numero(valor, nombre, decimales):
    try:
        numero = Decimal(str(valor or "0").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{nombre} no es válido.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError(f"{nombre} no puede ser negativo.")
    return numero.quantize(Decimal(decimales))


def registrar_parte(datos, *, orden, organizacion_id, unidad_negocio_id,
                    ParteProduccion, db_session, usuario_id=None):
    if int(orden.organizacion_id) != int(organizacion_id) or int(orden.unidad_negocio_id) != int(unidad_negocio_id):
        raise ValueError("La orden no pertenece al tenant y unidad activos.")
    if orden.estado != "aprobada":
        raise ValueError("Solo una orden aprobada admite partes preparatorios.")
    buena = _numero(datos.get("cantidad_buena"), "La cantidad buena", "0.000001")
    rechazada = _numero(datos.get("cantidad_rechazada"), "La cantidad rechazada", "0.000001")
    minutos = _numero(datos.get("minutos_reales"), "Los minutos reales", "0.0001")
    if buena + rechazada <= 0:
        raise ValueError("El parte debe informar alguna cantidad.")
    anterior = sum(
        Decimal(str(item.cantidad_buena)) + Decimal(str(item.cantidad_rechazada))
        for item in getattr(orden, "partes_informados", ()) if item.estado != "anulado"
    )
    if anterior + buena + rechazada > Decimal(str(orden.cantidad_planificada)):
        raise ValueError("El avance acumulado supera la cantidad planificada.")
    numero = str(datos.get("numero") or "").strip().upper()
    if not numero:
        raise ValueError("El número de parte es obligatorio.")
    parte = ParteProduccion(
        organizacion_id=organizacion_id, unidad_negocio_id=unidad_negocio_id,
        orden_produccion_id=orden.id, numero=numero,
        cantidad_buena=buena, cantidad_rechazada=rechazada,
        minutos_reales=minutos, estado="informado",
        impacta_inventario=False, consume_insumos=False,
        crea_producto_terminado=False,
        observacion=str(datos.get("observacion") or "").strip() or None,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(parte)
    db_session.commit()
    return parte


def resumir_orden(orden):
    partes = [item for item in getattr(orden, "partes_informados", ()) if item.estado != "anulado"]
    buenas = sum(Decimal(str(item.cantidad_buena)) for item in partes)
    rechazadas = sum(Decimal(str(item.cantidad_rechazada)) for item in partes)
    plan = Decimal(str(orden.cantidad_planificada))
    return {
        "buenas": buenas, "rechazadas": rechazadas,
        "informadas": buenas + rechazadas,
        "pendientes": plan - buenas - rechazadas,
        "minutos_reales": sum(Decimal(str(item.minutos_reales)) for item in partes),
    }
