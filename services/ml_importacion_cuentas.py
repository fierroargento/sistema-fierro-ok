"""
services/ml_importacion_cuentas.py

Asignación de cuenta Mercado Libre durante importación/webhook.

Regla SaaS:
- Todo Pedido ML nuevo debe nacer con ml_cuenta_id y ml_seller_id.
- Si la order trae seller_id, se resuelve por seller.
- Si no trae seller_id y hay una sola cuenta, se permite fallback legacy.
- Si hay múltiples cuentas y no hay seller_id, no se adivina.
"""

from services.ml_cuentas import (
    MLCuentaError,
    cuenta_default,
    cuenta_por_seller_id,
)


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _log(logger_fn, *partes):
    if logger_fn:
        logger_fn(*partes)


def ml_extraer_seller_id_order_service(order):
    order = order or {}
    seller = order.get("seller") or {}

    return _normalizar_texto(
        order.get("seller_id")
        or order.get("seller_user_id")
        or seller.get("id")
    )


def ml_resolver_cuenta_desde_order_service(
    order,
    MercadoLibreCuenta,
    cuenta_ml=None,
    logger_fn=None,
):
    if cuenta_ml:
        return cuenta_ml

    seller_id = ml_extraer_seller_id_order_service(order)

    if seller_id:
        try:
            return cuenta_por_seller_id(
                seller_id,
                MercadoLibreCuenta=MercadoLibreCuenta,
            )
        except MLCuentaError as e:
            _log(
                logger_fn,
                f"[ML CUENTAS] No se pudo resolver cuenta por seller_id={seller_id}:",
                e,
            )

    try:
        return cuenta_default(MercadoLibreCuenta=MercadoLibreCuenta)
    except MLCuentaError as e:
        _log(
            logger_fn,
            "[ML CUENTAS] No se pudo resolver cuenta default para order ML:",
            e,
        )
        return None


def ml_asignar_cuenta_ml_a_pedido_service(
    pedido,
    order,
    MercadoLibreCuenta,
    cuenta_ml=None,
    logger_fn=None,
):
    if not pedido or getattr(pedido, "canal", None) != "Mercado Libre":
        return None

    cuenta = ml_resolver_cuenta_desde_order_service(
        order,
        MercadoLibreCuenta,
        cuenta_ml=cuenta_ml,
        logger_fn=logger_fn,
    )

    if not cuenta:
        return None

    cuenta_id = getattr(cuenta, "id", None)
    seller_id = _normalizar_texto(getattr(cuenta, "user_id_ml", ""))

    if not cuenta_id or not seller_id:
        _log(logger_fn, "[ML CUENTAS] Cuenta ML incompleta; no se asigna al pedido.")
        return None

    seller_actual = _normalizar_texto(getattr(pedido, "ml_seller_id", ""))
    cuenta_actual = getattr(pedido, "ml_cuenta_id", None)

    if seller_actual and seller_actual != seller_id:
        _log(
            logger_fn,
            f"[ML CUENTAS] Pedido #{getattr(pedido, 'id', '?')} cambia "
            f"ml_seller_id {seller_actual} -> {seller_id}",
        )

    if cuenta_actual and cuenta_actual != cuenta_id:
        _log(
            logger_fn,
            f"[ML CUENTAS] Pedido #{getattr(pedido, 'id', '?')} cambia "
            f"ml_cuenta_id {cuenta_actual} -> {cuenta_id}",
        )

    pedido.ml_cuenta_id = cuenta_id
    pedido.ml_seller_id = seller_id

    return cuenta


def ml_resolver_cuenta_ml_webhook_service(
    data,
    MercadoLibreCuenta,
    logger_fn=None,
):
    data = data or {}
    seller_id = _normalizar_texto(data.get("user_id"))

    if not seller_id:
        return None

    try:
        return cuenta_por_seller_id(
            seller_id,
            MercadoLibreCuenta=MercadoLibreCuenta,
        )
    except MLCuentaError as e:
        _log(
            logger_fn,
            f"[WEBHOOK ML] No se pudo resolver cuenta ML user_id={seller_id}:",
            e,
        )
        return None
