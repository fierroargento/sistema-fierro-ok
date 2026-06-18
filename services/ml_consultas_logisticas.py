"""
services/ml_consultas_logisticas.py
──────────────────────────────────
Consultas logísticas simples de ML/Acordás que el bot sí puede responder.

APB:
- "Cuánto demora" no debe escalar a operador si es una consulta simple.
- Reclamos, enojo, cancelaciones, problemas o cambios de modalidad siguen yendo a operador.
"""

import unicodedata


def _normalizar(valor):
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return " ".join(texto.split())


def detectar_consulta_demora_simple_ml(pedido):
    if not pedido:
        return False

    resumen = _normalizar(getattr(pedido, "ia_resumen", ""))

    if not resumen:
        return False

    menciona_demora = any(
        marca in resumen
        for marca in [
            "pregunta por demora",
            "pregunta demora",
            "cuanto demora",
            "cuanto tarda",
            "cuando llega",
            "cuando llegaria",
            "tiempo de entrega",
            "demora habitual",
        ]
    )

    if not menciona_demora:
        return False

    bloqueadores_operador = [
        "reclamo",
        "problema",
        "enojo",
        "insulto",
        "cancel",
        "devolucion",
        "producto roto",
        "producto incorrecto",
        "no llego",
        "llego tarde",
        "cambio de modalidad",
        "retirar personalmente",
        "retiro",
    ]

    return not any(marca in resumen for marca in bloqueadores_operador)


def texto_demora_handoff_wa_ml():
    return (
        "La demora habitual es de entre 3 y 5 días hábiles a partir del despacho.\n\n"
        "Para seguir con la coordinación del envío, en breve te vamos a escribir por WhatsApp."
    )


def limpiar_derivacion_operador_por_demora_simple(pedido):
    if not detectar_consulta_demora_simple_ml(pedido):
        return False

    try:
        pedido.ia_requiere_operador = False
    except Exception:
        pass

    try:
        if str(getattr(pedido, "ia_recolector_estado", "") or "").strip().lower() == "requiere_operador":
            pedido.ia_recolector_estado = "datos_completos"
    except Exception:
        pass

    return True
