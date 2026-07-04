"""
services/ia_recolector_logistica.py

Reglas de reencauce del recolector IA hacia logística automática.

Objetivo SaaS/CRM:
- Mantener reglas fuera de app.py.
- No depender de una cuenta ML global.
- Tomar decisiones por pedido.
- No borrar escalados duros a operador.
"""

MOTIVOS_OPERADOR_DUROS = [
    "cancel",
    "anular",
    "devolucion",
    "devolución",
    "reclamo",
    "problema",
    "enojo",
    "insulto",
    "cambio de modalidad",
    "cambiar modalidad",
    "quiero retirar",
    "retiro personalmente",
    "retirar personalmente",
    "no quiero envio",
    "no quiero envío",
]


def _texto_operador(resultado):
    resultado = resultado or {}

    return " ".join([
        str(resultado.get("resumen") or ""),
        str(resultado.get("motivo_operador") or ""),
        str(resultado.get("estado") or ""),
    ]).strip().lower()


def tiene_motivo_operador_duro_recolector(resultado):
    texto = _texto_operador(resultado)

    return any(
        motivo in texto
        for motivo in MOTIVOS_OPERADOR_DUROS
    )


def debe_reencauzar_pp6040_sin_faltantes_service(
    pedido,
    resultado,
    faltantes,
    requiere_operador_final,
    es_ml_acordas_entrega_fn,
    pedido_es_plegable_pp6040_fn,
):
    """
    Permite que la logística automática continúe cuando:
    - el pedido es ML Acordás,
    - es PP6040/plegable,
    - ya no hay faltantes reales,
    - requiere_operador viene de una marca blanda/vieja,
    - no hay un motivo duro que sí deba ver un operador.
    """
    if not pedido:
        return False

    if not requiere_operador_final:
        return False

    if faltantes:
        return False

    if not es_ml_acordas_entrega_fn(pedido):
        return False

    if not pedido_es_plegable_pp6040_fn(pedido):
        return False

    if tiene_motivo_operador_duro_recolector(resultado):
        return False

    return True
