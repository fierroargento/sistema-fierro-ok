"""
services/logistica_defaults.py
─────────────────────────────
Defaults logísticos seguros para pedidos.

Este módulo concentra reglas de asignación inicial de transporte/tipo de entrega
para evitar seguir haciendo crecer app.py con reglas de negocio.
"""


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
    Detecta parrilla plegable PP6040 para NO forzar Vía Cargo.

    APB:
    - PP6040 tiene regla logística especial y no debe entrar por el default
      general de ML/Acordás → Vía Cargo/Sucursal.
    - La detección mira SKU y descripción de los items, sin depender de app.py.
    """
    if not pedido:
        return False

    for item in (getattr(pedido, "items", None) or []):
        sku = _texto_normalizado(getattr(item, "sku", "")).upper()
        descripcion = _texto_normalizado(getattr(item, "descripcion", "")).upper()

        if "PP6040" in sku or "PP6040" in descripcion or "PLEGABLE" in descripcion:
            return True

    return False


def aplicar_default_via_cargo_sucursal_ml_acordas(pedido):
    """
    Aplica default logístico para Mercado Libre / Acordás la Entrega.

    Regla actual Fierro:
    - ML + Acordás la Entrega + NO PP6040 => Vía Cargo / Sucursal.
    - La sucursal se elige después, pero transporte y tipo de entrega deben
      quedar definidos apenas los datos del cliente están completos.

    Devuelve True si modificó el pedido.
    """
    if not es_ml_acordas_entrega_service(pedido):
        return False

    if pedido_es_plegable_pp6040_service(pedido):
        return False

    modificado = False

    if not str(getattr(pedido, "empresa_envio", "") or "").strip():
        pedido.empresa_envio = "Vía Cargo"
        modificado = True

    if not str(getattr(pedido, "tipo_entrega", "") or "").strip():
        pedido.tipo_entrega = "Sucursal"
        modificado = True

    return modificado