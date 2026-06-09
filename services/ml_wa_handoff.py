"""
services/ml_wa_handoff.py
─────────────────────────
Reglas APB para transición Mercado Libre → WhatsApp.

Objetivo:
- ML no debe quedar en silencio cuando el comprador completa datos.
- La transición debe avisarse por ML antes o durante el inicio WA.
- No iniciar cross-sell hasta que el cliente responda por WhatsApp y abra ventana.
"""

MARCA_TRANSICION_ML_WA = "ML avisó migración a WhatsApp"


def texto_transicion_ml_wa_datos_completos():
    return (
        "Gracias, ya tenemos los datos necesarios. "
        "En breve te vamos a enviar más información sobre tu envío por WhatsApp."
    )


def debe_avisar_transicion_ml_wa(pedido):
    resumen = str(getattr(pedido, "ia_resumen", "") or "")
    return MARCA_TRANSICION_ML_WA not in resumen


def marcar_transicion_ml_wa_en_resumen(pedido):
    if not pedido:
        return ""

    resumen = str(getattr(pedido, "ia_resumen", "") or "").strip()

    if MARCA_TRANSICION_ML_WA not in resumen:
        resumen = f"{resumen} | {MARCA_TRANSICION_ML_WA}".strip(" |")
        try:
            pedido.ia_resumen = resumen[:1000]
        except Exception:
            pass

    return resumen
