"""
services.wa_auto_ml_decision
----------------------------
Decisiones puras para inicio automatico WhatsApp desde Mercado Libre.

APB / SaaS:
- No escribe DB.
- No envia mensajes.
- No depende de Flask ni app.py.
- Solo normaliza/decide datos para que app.py ejecute.
"""


def limpiar_faltantes_para_handoff_wa(
    pedido,
    faltantes=None,
    telefono_normalizado="",
):
    """
    Limpia faltantes antes de decidir si WhatsApp puede tomar la posta.

    Reglas:
    - Ignora vacios.
    - Si el telefono ya esta normalizado, no lo considera faltante.
    - Si localidad/provincia ya existen en el pedido, no las considera faltantes.
    - Deduplica manteniendo orden.
    """
    faltantes_limpios = []
    tel = str(telefono_normalizado or "").strip()

    for campo in (faltantes or []):
        campo = str(campo or "").strip()

        if not campo:
            continue

        if campo == "telefono" and tel:
            continue

        if campo in ["localidad", "provincia"] and getattr(pedido, campo, None):
            continue

        if campo not in faltantes_limpios:
            faltantes_limpios.append(campo)

    return faltantes_limpios

def construir_marca_ml_sigue_recolectando(faltantes_limpios):
    """
    Construye la marca de resumen cuando ML sigue recolectando
    y WhatsApp no debe tomar la posta todavia.
    """
    faltantes = []

    for campo in (faltantes_limpios or []):
        campo = str(campo or "").strip()
        if campo:
            faltantes.append(campo)

    if not faltantes:
        return "ML sigue recolectando datos; WA no iniciado por faltantes"

    return (
        "ML sigue recolectando datos; WA no iniciado por faltantes: "
        + ", ".join(faltantes)
    )
