"""Conciliación interna de facturas contra recepciones, sin efectos externos."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _centavos(valor):
    try:
        numero = Decimal(str(valor or "").replace(".", "").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("El total del comprobante no es válido.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError("El total del comprobante no puede ser negativo.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def registrar_factura_preparatoria(datos, *, recepcion, organizacion_id,
                                    unidad_negocio_id, FacturaProveedorCompra,
                                    db_session, usuario_id=None):
    if (
        int(recepcion.organizacion_id) != int(organizacion_id)
        or int(recepcion.unidad_negocio_id) != int(unidad_negocio_id)
    ):
        raise ValueError("La recepción no pertenece al tenant y unidad activos.")
    if recepcion.estado == "anulada":
        raise ValueError("Una recepción anulada no admite comprobantes.")
    total = _centavos(datos.get("total"))
    esperado = int(recepcion.subtotal_centavos)
    diferencia = total - esperado
    motivos = []
    if total != esperado:
        motivos.append(
            f"Diferencia de importe: comprobante {total}, recepción {esperado} centavos."
        )
    tipo = str(datos.get("tipo_comprobante") or "").strip().upper()
    punto = str(datos.get("punto_venta") or "").strip().zfill(5)
    numero = str(datos.get("numero") or "").strip().zfill(8)
    if not tipo or not punto.strip("0") or not numero.strip("0"):
        raise ValueError("Tipo, punto de venta y número son obligatorios.")
    factura = FacturaProveedorCompra(
        organizacion_id=organizacion_id,
        unidad_negocio_id=unidad_negocio_id,
        proveedor_id=recepcion.orden.proveedor_id,
        orden_compra_id=recepcion.orden_compra_id,
        recepcion_compra_id=recepcion.id,
        tipo_comprobante=tipo, punto_venta=punto, numero=numero,
        total_centavos=total, diferencia_centavos=diferencia,
        estado="observada" if motivos else "conciliada",
        motivo_observacion=" ".join(motivos) or None,
        impacta_fiscal=False, obligacion_creada=False,
        creado_por_usuario_id=usuario_id,
    )
    db_session.add(factura)
    db_session.commit()
    return factura


def resumen_conciliacion(facturas):
    return {
        "total": len(facturas),
        "conciliadas": sum(item.estado == "conciliada" for item in facturas),
        "observadas": sum(item.estado == "observada" for item in facturas),
        "diferencia_centavos": sum(int(item.diferencia_centavos) for item in facturas),
        "impactos_ejecutados": 0,
    }
