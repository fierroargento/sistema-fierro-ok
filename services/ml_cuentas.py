"""
services/ml_cuentas.py

Resolución de cuentas Mercado Libre para arquitectura multicuenta/SaaS.

Reglas:
- ml_cuenta_id en Pedido es la referencia autoritativa.
- ml_seller_id en Pedido es snapshot/auditoría, no reemplaza la FK.
- No usar MercadoLibreCuenta.query.first() como resolución runtime cuando hay más de una cuenta.
- Este servicio no llama a la API de Mercado Libre.
"""

CANAL_MERCADO_LIBRE = "Mercado Libre"


class MLCuentaError(Exception):
    """Error base de resolución de cuenta Mercado Libre."""


class MLCuentaNoConfigurada(MLCuentaError):
    """No hay cuentas ML configuradas."""


class MLCuentaAmbigua(MLCuentaError):
    """Hay más de una cuenta y no se puede elegir una por defecto de forma segura."""


class MLCuentaNoAsignada(MLCuentaError):
    """El pedido ML no tiene cuenta ML asignada."""


class MLCuentaNoEncontrada(MLCuentaError):
    """No se encontró la cuenta ML solicitada."""


class MLCuentaInconsistente(MLCuentaError):
    """El pedido tiene datos ML inconsistentes con la cuenta asociada."""


def _normalizar_texto(valor):
    return str(valor or "").strip()


def _modelo_cuenta(MercadoLibreCuenta=None):
    if MercadoLibreCuenta is not None:
        return MercadoLibreCuenta

    from app import MercadoLibreCuenta as MercadoLibreCuentaApp
    return MercadoLibreCuentaApp


def es_pedido_mercado_libre(pedido):
    return _normalizar_texto(getattr(pedido, "canal", "")) == CANAL_MERCADO_LIBRE


def cuenta_default(MercadoLibreCuenta=None):
    """Devuelve la única cuenta ML existente.

    Uso permitido:
    - compatibilidad legacy
    - pantallas/admin
    - backfills controlados

    No debe usarse para operar pedidos cuando ya existe ml_cuenta_id.
    """
    ModeloCuenta = _modelo_cuenta(MercadoLibreCuenta)
    cuentas = list(ModeloCuenta.query.all() or [])

    if not cuentas:
        raise MLCuentaNoConfigurada("No hay cuentas Mercado Libre configuradas.")

    if len(cuentas) > 1:
        raise MLCuentaAmbigua(
            "Hay más de una cuenta Mercado Libre; no se puede elegir una default segura."
        )

    return cuentas[0]


def cuenta_por_id(ml_cuenta_id, MercadoLibreCuenta=None):
    ml_cuenta_id = _normalizar_texto(ml_cuenta_id)
    if not ml_cuenta_id:
        raise MLCuentaNoAsignada("El pedido ML no tiene ml_cuenta_id asignado.")

    ModeloCuenta = _modelo_cuenta(MercadoLibreCuenta)

    cuenta = None

    try:
        cuenta = ModeloCuenta.query.get(int(ml_cuenta_id))
    except Exception:
        try:
            cuenta = ModeloCuenta.query.filter_by(id=int(ml_cuenta_id)).first()
        except Exception:
            cuenta = None

    if not cuenta:
        raise MLCuentaNoEncontrada(
            f"No se encontró MercadoLibreCuenta id={ml_cuenta_id}."
        )

    return cuenta


def cuenta_por_seller_id(seller_id, MercadoLibreCuenta=None):
    seller_id = _normalizar_texto(seller_id)
    if not seller_id:
        raise MLCuentaNoAsignada("No se recibió seller_id/user_id_ml para resolver cuenta ML.")

    ModeloCuenta = _modelo_cuenta(MercadoLibreCuenta)

    cuenta = ModeloCuenta.query.filter_by(user_id_ml=seller_id).first()
    if not cuenta:
        raise MLCuentaNoEncontrada(
            f"No se encontró MercadoLibreCuenta user_id_ml={seller_id}."
        )

    return cuenta


def validar_snapshot_pedido_cuenta(pedido, cuenta):
    """Valida que ml_seller_id del pedido coincida con user_id_ml de la cuenta.

    ml_seller_id es snapshot: sirve para detectar datos cruzados.
    La FK ml_cuenta_id sigue siendo la referencia autoritativa.
    """
    seller_pedido = _normalizar_texto(getattr(pedido, "ml_seller_id", ""))
    seller_cuenta = _normalizar_texto(getattr(cuenta, "user_id_ml", ""))

    if seller_pedido and seller_cuenta and seller_pedido != seller_cuenta:
        raise MLCuentaInconsistente(
            "El pedido ML tiene ml_seller_id distinto al user_id_ml de su cuenta."
        )

    return True


def cuenta_por_pedido(pedido, MercadoLibreCuenta=None, validar_snapshot=True):
    """Resuelve la cuenta Mercado Libre autoritativa para un pedido.

    En etapa SaaS/multicuenta, toda operación ML sobre un pedido debe pasar por acá.
    """
    if not pedido:
        raise MLCuentaNoAsignada("No se recibió pedido para resolver cuenta ML.")

    if not es_pedido_mercado_libre(pedido):
        raise MLCuentaNoAsignada("El pedido no pertenece al canal Mercado Libre.")

    ml_cuenta_id = getattr(pedido, "ml_cuenta_id", None)
    if not ml_cuenta_id:
        raise MLCuentaNoAsignada("Pedido Mercado Libre sin ml_cuenta_id asignado.")

    cuenta = cuenta_por_id(ml_cuenta_id, MercadoLibreCuenta=MercadoLibreCuenta)

    if validar_snapshot:
        validar_snapshot_pedido_cuenta(pedido, cuenta)

    return cuenta


def seller_id_pedido(pedido, MercadoLibreCuenta=None):
    cuenta = cuenta_por_pedido(pedido, MercadoLibreCuenta=MercadoLibreCuenta)
    seller_id = _normalizar_texto(getattr(cuenta, "user_id_ml", ""))

    if not seller_id:
        raise MLCuentaInconsistente("La cuenta ML del pedido no tiene user_id_ml.")

    return seller_id


def cuentas_activas(MercadoLibreCuenta=None):
    """Devuelve cuentas conectadas/activas sin elegir una arbitrariamente."""
    ModeloCuenta = _modelo_cuenta(MercadoLibreCuenta)

    try:
        return list(
            ModeloCuenta.query
            .filter_by(estado_conexion="conectada")
            .all()
            or []
        )
    except Exception:
        cuentas = list(ModeloCuenta.query.all() or [])
        return [
            c for c in cuentas
            if _normalizar_texto(getattr(c, "estado_conexion", "")) == "conectada"
        ]
