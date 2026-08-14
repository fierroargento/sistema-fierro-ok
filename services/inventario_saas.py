"""Reglas de reservas, transferencias y conteos del inventario SaaS.

No importa pedidos ni sincroniza canales. Los integradores futuros deben usar
claves idempotentes para que un mismo evento nunca descuente dos veces.
"""

import json

from services.fechas import ahora_utc_naive
from services.inventario_nucleo import registrar_movimiento, stock_disponible


ESTADOS_RESERVA = frozenset({"activa", "liberada", "consumida", "vencida"})
ESTADOS_TRANSFERENCIA = frozenset(
    {"borrador", "despachada", "parcial", "recibida", "cancelada"}
)


def preparar_items_catalogo(
    organizacion_id, inclusiones, *, ItemInventario, db_session,
):
    """Proyecta SKU principal y variantes; nunca activa stock ni canales."""
    creados = 0
    for inclusion in inclusiones:
        catalogo = getattr(inclusion, "catalogo", None)
        if int(getattr(catalogo, "organizacion_id", 0) or 0) != int(organizacion_id):
            continue
        filas = [{
            "sku": inclusion.sku_comercial,
            "nombre": inclusion.nombre_comercial,
            "tipo": "producto",
            "atributos": {},
        }]
        try:
            variantes = json.loads(inclusion.variantes_json or "[]")
        except (TypeError, ValueError):
            variantes = []
        for variante in variantes if isinstance(variantes, list) else []:
            if not isinstance(variante, dict) or not str(variante.get("sku") or "").strip():
                continue
            filas.append({
                "sku": variante["sku"],
                "nombre": f"{inclusion.nombre_comercial} · {variante.get('opciones') or 'Variante'}",
                "tipo": "variante",
                "atributos": variante,
            })
        for fila in filas:
            sku = str(fila["sku"] or "").strip()[:100]
            if not sku:
                continue
            item = ItemInventario.query.filter_by(
                organizacion_id=organizacion_id, sku=sku,
            ).first()
            if item is None:
                item = ItemInventario(
                    organizacion_id=organizacion_id,
                    producto_id=inclusion.producto_id,
                    catalogo_producto_id=inclusion.id,
                    sku=sku,
                    nombre=str(fila["nombre"] or sku)[:220],
                    tipo=fila["tipo"],
                    atributos_json=json.dumps(
                        fila["atributos"], ensure_ascii=False, separators=(",", ":"),
                    ),
                    activo=False,
                )
                db_session.add(item)
                creados += 1
            else:
                item.nombre = str(fila["nombre"] or sku)[:220]
                item.catalogo_producto_id = inclusion.id
                item.atributos_json = json.dumps(
                    fila["atributos"], ensure_ascii=False, separators=(",", ":"),
                )
    db_session.commit()
    return creados


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
        confirmar=False,
    )
    db_session.commit()
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
        db_session=db_session, confirmar=False,
    )
    if estado == "consumida":
        registrar_movimiento(
            existencia, tipo="egreso", cantidad=reserva.cantidad,
            motivo="Venta confirmada", referencia=reserva.referencia_externa,
            usuario=usuario, MovimientoInventario=MovimientoInventario,
            db_session=db_session, confirmar=False,
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
        confirmar=False,
    )
    transferencia.destino.stock_transito = (
        int(transferencia.destino.stock_transito or 0) + cantidad
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
        db_session=db_session, confirmar=False,
    )
    transferencia.destino.stock_transito = max(
        0,
        int(transferencia.destino.stock_transito or 0) - cantidad,
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


def conciliar_conteo(
    conteo, *, MovimientoInventario, db_session, usuario="admin",
):
    if conteo.estado == "conciliado":
        return conteo
    if conteo.estado not in {"abierto", "contado"}:
        raise ValueError("El inventario no está disponible para conciliación.")
    if not conteo.items:
        raise ValueError("El inventario no contiene existencias.")
    for item in conteo.items:
        if item.cantidad_contada is None:
            raise ValueError("Faltan cantidades por contar.")
        diferencia = diferencia_conteo(item.cantidad_esperada, item.cantidad_contada)
        item.diferencia = diferencia
        if diferencia:
            registrar_movimiento(
                item.existencia, tipo="ajuste", cantidad=diferencia,
                motivo=f"Conciliación {conteo.codigo}", referencia=conteo.codigo,
                usuario=usuario, MovimientoInventario=MovimientoInventario,
                db_session=db_session, confirmar=False,
            )
    conteo.estado = "conciliado"
    conteo.usuario_concilia = usuario
    conteo.fecha_conciliacion = ahora_utc_naive()
    db_session.commit()
    return conteo
