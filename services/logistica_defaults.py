"""
services/logistica_defaults.py
─────────────────────────────
Defaults logísticos seguros para pedidos.

Este módulo concentra reglas de asignación inicial de transporte/tipo de entrega
para evitar seguir haciendo crecer app.py con reglas de negocio.
"""

from services.logistica_catalogo import calcular_logistica_pedido_desde_catalogo


def _texto_normalizado(valor):
    return str(valor or "").strip().lower()


def es_ml_acordas_entrega_service(pedido):
    return bool(
        pedido
        and getattr(pedido, "canal", None) == "Mercado Libre"
        and getattr(pedido, "ml_tipo", None) == "Acordás la Entrega"
    )


def pedido_es_plegable_pp6040_service(pedido):
    """
    Detecta familia PP6040 usando solo SKU.

    APB:
    - La regla se centraliza en domain/productos.py.
    - No mira descripción ni observaciones.
    - PA9060H no entra como PP6040.
    """
    if not pedido:
        return False

    from domain.productos import pedido_tiene_pp6040
    return pedido_tiene_pp6040(pedido)


def _cp_destino_pedido(pedido):
    return (
        getattr(pedido, "codigo_postal", None)
        or getattr(pedido, "cp", None)
        or getattr(pedido, "codigo_postal_destino", None)
    )


def _cotizar_correo_sucursal_acordas(pedido, cotizar_correo_fn=None):
    cp_destino = _cp_destino_pedido(pedido)
    if not cp_destino:
        return None

    logistica = calcular_logistica_pedido_desde_catalogo(pedido)
    if not logistica.get("ok") or not logistica.get("permite_correo", True):
        return None

    cotizador = cotizar_correo_fn
    if cotizador is None:
        from modules.transportes.correo_argentino import cotizar_correo
        cotizador = cotizar_correo

    try:
        return cotizador(
            cp_destino,
            "S",
            peso_gr=logistica.get("peso_gr"),
            alto_cm=logistica.get("alto_cm"),
            ancho_cm=logistica.get("ancho_cm"),
            largo_cm=logistica.get("largo_cm"),
        )
    except Exception:
        return None


def _aplicar_correo_sucursal_acordas(pedido, decision):
    pedido.empresa_envio = "Correo Argentino"
    pedido.tipo_entrega = "Sucursal"

    precio = decision.get("precio", 0)

    if hasattr(pedido, "costo_envio_sucursal"):
        pedido.costo_envio_sucursal = precio

    if hasattr(pedido, "costo_envio"):
        pedido.costo_envio = precio

    resumen_actual = str(getattr(pedido, "ia_resumen", "") or "").strip()
    marca = f"TRANSPORTE: Correo Argentino sucursal priorizado por costo (${precio:.0f})"

    if marca not in resumen_actual:
        pedido.ia_resumen = f"{resumen_actual} | {marca}".strip(" |")


def aplicar_default_via_cargo_sucursal_ml_acordas(pedido, cotizar_correo_fn=None):
    """
    Aplica default logístico para Mercado Libre / Acordás la Entrega.

    Regla Fierro:
    - ML + Acordás la Entrega + PP6040: no entra acá, usa regla propia Correo.
    - ML + Acordás la Entrega + NO PP6040:
        1) Si Correo sucursal cotiza <= umbral configurado, prioriza Correo.
        2) Si no, mantiene default histórico: Vía Cargo / Sucursal.

    El umbral se configura con:
    CORREO_MAX_COSTO_SUCURSAL_ACORDAS

    Con umbral 0, no cambia el comportamiento actual.

    Devuelve True si modificó el pedido.
    """
    if not es_ml_acordas_entrega_service(pedido):
        return False

    if pedido_es_plegable_pp6040_service(pedido):
        return False

    empresa_actual = str(getattr(pedido, "empresa_envio", "") or "").strip()
    tipo_actual = str(getattr(pedido, "tipo_entrega", "") or "").strip()

    # No pisar decisiones ya tomadas por operador, IA u otro flujo.
    if empresa_actual and tipo_actual:
        return False

    try:
        from services.correo_argentino_operacion import evaluar_prioridad_correo_sucursal_acordas

        cotizacion_correo = _cotizar_correo_sucursal_acordas(
            pedido,
            cotizar_correo_fn=cotizar_correo_fn,
        )

        decision_correo = evaluar_prioridad_correo_sucursal_acordas(
            cotizacion_correo,
            es_acordas=True,
            es_pp6040=False,
        )

        if decision_correo.get("usar_correo"):
            _aplicar_correo_sucursal_acordas(pedido, decision_correo)
            return True
    except Exception:
        pass

    modificado = False

    if not empresa_actual:
        pedido.empresa_envio = "Vía Cargo"
        modificado = True

    if not tipo_actual:
        pedido.tipo_entrega = "Sucursal"
        modificado = True

    return modificado
