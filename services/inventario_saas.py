"""Reglas de reservas, transferencias y conteos del inventario SaaS.

No importa pedidos ni sincroniza canales. Los integradores futuros deben usar
claves idempotentes para que un mismo evento nunca descuente dos veces.
"""

from services.fechas import ahora_utc_naive
from services.inventario_nucleo import registrar_movimiento, stock_disponible


ESTADOS_RESERVA = frozenset({"activa", "liberada", "consumida", "vencida"})
ESTADOS_TRANSFERENCIA = frozenset(
    {"borrador", "despachada", "parcial", "recibida", "cancelada"}
)


def validar_mismo_tenant(organizacion_id, *registros):
    for registro in registros:
        if int(getattr(registro, "organizacion_id", 0) or 0) != int(organizacion_id):
            raise ValueError("La operación mezcla registros de otra organización.")


def crear_reserva(
    existencia, *, canal, referencia_externa, clave_idempotencia, cantidad,
    ReservaInventario, MovimientoInventario, db_session, vence_en=None,
    motivo="Reserva por canal", usuario="sistema",
):
    clave = str(clave_idempotencia or "").strip()
    if not clave:
        raise ValueError("La reserva necesita una clave idempotente.")
    previa = ReservaInventario.query.filter_by(
        organizacion_id=existencia.organizacion_id,
        clave_idempotencia=clave,
    ).first()
    if previa is not None:
        return previa
    cantidad = int(cantidad)
    if cantidad <= 0 or stock_disponible(existencia) < cantidad:
        raise ValueError("No hay stock disponible suficiente para reservar.")
    reserva = ReservaInventario(
        organizacion_id=existencia.organizacion_id,
        existencia_sucursal_id=existencia.id,
        canal=str(canal or "interno").strip()[:50],
        referencia_externa=str(referencia_externa or "").strip()[:150],
        clave_idempotencia=clave[:180], cantidad=cantidad, estado="activa",
        vence_en=vence_en, motivo=str(motivo or "Reserva")[:300],
    )
    db_session.add(reserva)
    registrar_movimiento(
        existencia, tipo="reserva", cantidad=cantidad, motivo=motivo,
        referencia=referencia_externa, usuario=usuario,
        MovimientoInventario=MovimientoInventario, db_session=db_session,
    )
    return reserva


def cerrar_reserva(
    reserva, *, estado, MovimientoInventario, db_session, usuario="sistema",
):
    if estado not in {"liberada", "consumida", "vencida"}:
        raise ValueError("El cierre de la reserva no es válido.")
    if reserva.estado != "activa":
        return reserva
    existencia = reserva.existencia
    registrar_movimiento(
        existencia, tipo="liberacion", cantidad=reserva.cantidad,
        motivo=f"Reserva {estado}", referencia=reserva.referencia_externa,
        usuario=usuario, MovimientoInventario=MovimientoInventario,
        db_session=db_session,
    )
    if estado == "consumida":
        registrar_movimiento(
            existencia, tipo="egreso", cantidad=reserva.cantidad,
            motivo="Venta confirmada", referencia=reserva.referencia_externa,
            usuario=usuario, MovimientoInventario=MovimientoInventario,
            db_session=db_session,
        )
    reserva.estado = estado
    reserva.fecha_cierre = ahora_utc_naive()
    db_session.commit()
    return reserva


def validar_transferencia(transferencia):
    validar_mismo_tenant(
        transferencia.organizacion_id, transferencia.origen, transferencia.destino,
    )
    if transferencia.origen.id == transferencia.destino.id:
        raise ValueError("El origen y el destino deben ser diferentes.")
    if transferencia.origen.producto_id != transferencia.destino.producto_id:
        raise ValueError("El origen y el destino deben corresponder al mismo producto.")
    if int(transferencia.cantidad_solicitada) <= 0:
        raise ValueError("La transferencia necesita una cantidad positiva.")
    return True


def despachar_transferencia(
    transferencia, *, MovimientoInventario, db_session, usuario="admin",
):
    validar_transferencia(transferencia)
    if transferencia.estado != "borrador":
        return transferencia
    cantidad = int(transferencia.cantidad_solicitada)
    registrar_movimiento(
        transferencia.origen, tipo="egreso", cantidad=cantidad,
        motivo=f"Transferencia {transferencia.codigo}",
        referencia=transferencia.codigo, usuario=usuario,
        MovimientoInventario=MovimientoInventario, db_session=db_session,
    )
    transferencia.cantidad_despachada = cantidad
    transferencia.estado = "despachada"
    transferencia.usuario_despacha = usuario
    transferencia.fecha_despacho = ahora_utc_naive()
    db_session.commit()
    return transferencia


def recibir_transferencia(
    transferencia, cantidad, *, MovimientoInventario, db_session, usuario="admin",
):
    if transferencia.estado not in {"despachada", "parcial"}:
        raise ValueError("La transferencia no está disponible para recepción.")
    cantidad = int(cantidad)
    pendiente = int(transferencia.cantidad_despachada) - int(transferencia.cantidad_recibida)
    if cantidad <= 0 or cantidad > pendiente:
        raise ValueError("La cantidad recibida supera el saldo en tránsito.")
    registrar_movimiento(
        transferencia.destino, tipo="ingreso", cantidad=cantidad,
        motivo=f"Recepción {transferencia.codigo}", referencia=transferencia.codigo,
        usuario=usuario, MovimientoInventario=MovimientoInventario,
        db_session=db_session,
    )
    transferencia.cantidad_recibida += cantidad
    transferencia.estado = (
        "recibida" if transferencia.cantidad_recibida == transferencia.cantidad_despachada
        else "parcial"
    )
    transferencia.usuario_recibe = usuario
    if transferencia.estado == "recibida":
        transferencia.fecha_recepcion = ahora_utc_naive()
    db_session.commit()
    return transferencia


def diferencia_conteo(cantidad_esperada, cantidad_contada):
    esperada = int(cantidad_esperada)
    contada = int(cantidad_contada)
    if contada < 0:
        raise ValueError("La cantidad contada no puede ser negativa.")
    return contada - esperada
