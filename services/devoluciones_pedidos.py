"""Validaciones puras para registrar devoluciones históricas de pedidos."""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from services.acceso_tenant_pedidos import validar_pedido_en_tenant


ESTADOS_DEVOLUCION = frozenset({"completa", "parcial", "danada"})
ESTADOS_ITEM_DEVOLUCION = frozenset({"ok", "parcial", "danado"})
RESULTADOS_RECLAMO_ML = frozenset({"reintegrado", "rechazado", "parcial"})


@dataclass(frozen=True)
class ItemDevolucionValidado:
    item: object
    estado: str
    cantidad_ok: int
    cantidad_danada: int
    observacion: str


def validar_devolucion_pedido(
    pedido, datos, *, organizacion_id, unidad_negocio_id,
):
    validar_pedido_en_tenant(pedido, organizacion_id, unidad_negocio_id)
    if pedido.estado != "No entregado":
        raise ValueError("El pedido no admite una devolución en su estado actual.")

    try:
        fecha = datetime.strptime(
            str(datos.get("fecha_devolucion") or "").strip(), "%Y-%m-%dT%H:%M"
        )
    except ValueError as error:
        raise ValueError("La fecha de devolución no tiene un formato válido.") from error

    estado = str(datos.get("estado_devolucion") or "").strip()
    observacion = str(datos.get("observacion_devolucion") or "").strip()
    if estado not in ESTADOS_DEVOLUCION:
        raise ValueError("El estado de la devolución no es válido.")
    if len(observacion) > 300:
        raise ValueError("La observación de la devolución supera 300 caracteres.")

    items = []
    for item in pedido.items:
        estado_item = str(datos.get(f"estado_item_{item.id}") or "").strip()
        observacion_item = str(datos.get(f"obs_item_{item.id}") or "").strip()
        try:
            cantidad_ok = int(str(datos.get(f"cantidad_ok_{item.id}") or "0").strip())
            cantidad_danada = int(str(datos.get(f"cantidad_danada_{item.id}") or "0").strip())
        except ValueError as error:
            raise ValueError(f"Las cantidades del item {item.sku} no son válidas.") from error

        total = int(item.cantidad or 0)
        if estado_item not in ESTADOS_ITEM_DEVOLUCION:
            raise ValueError(f"El estado del item {item.sku} no es válido.")
        if len(observacion_item) > 300:
            raise ValueError(f"La observación del item {item.sku} supera 300 caracteres.")
        if cantidad_ok < 0 or cantidad_danada < 0:
            raise ValueError(f"Las cantidades del item {item.sku} no pueden ser negativas.")
        if cantidad_ok + cantidad_danada <= 0:
            raise ValueError(f"Tenés que indicar al menos una cantidad para el item {item.sku}.")
        if cantidad_ok + cantidad_danada > total:
            raise ValueError(f"La suma de cantidades del item {item.sku} supera la cantidad original.")
        if estado_item == "ok" and cantidad_danada:
            raise ValueError(f"El item {item.sku} está marcado como OK pero tiene cantidad dañada.")
        if estado_item == "danado" and cantidad_ok:
            raise ValueError(f"El item {item.sku} está marcado como dañado pero tiene cantidad OK.")
        items.append(ItemDevolucionValidado(
            item, estado_item, cantidad_ok, cantidad_danada, observacion_item
        ))

    return fecha, estado, observacion, tuple(items)


def validar_cierre_reclamo_ml(
    pedido, datos, *, organizacion_id, unidad_negocio_id,
):
    validar_pedido_en_tenant(pedido, organizacion_id, unidad_negocio_id)
    if pedido.estado != "Reclamar a Mercado Libre" or pedido.canal != "Mercado Libre":
        raise ValueError("El pedido no admite el cierre de un reclamo de Mercado Libre.")
    numero = str(datos.get("numero_reclamo_ml") or "").strip()
    resultado = str(datos.get("resultado_reclamo_ml") or "").strip()
    observacion = str(datos.get("observacion_reclamo_ml") or "").strip()
    try:
        monto = float(str(datos.get("monto_recuperado_ml") or "").replace(",", "."))
    except ValueError as error:
        raise ValueError("El monto recuperado no es válido.") from error
    if not numero or len(numero) > 100:
        raise ValueError("El número de reclamo de Mercado Libre no es válido.")
    if resultado not in RESULTADOS_RECLAMO_ML:
        raise ValueError("El resultado del reclamo no es válido.")
    if not isfinite(monto) or monto < 0:
        raise ValueError("El monto recuperado no es válido.")
    if len(observacion) > 300:
        raise ValueError("La observación del reclamo supera 300 caracteres.")
    return numero, resultado, monto, observacion
