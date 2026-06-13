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

def agregar_marca_a_resumen_si_falta(resumen_actual, marca, limite=1000):
    """
    Agrega una marca al resumen solo si todavia no existe.

    Mantiene la logica historica de app.py:
    - usa separador " | "
    - limpia separadores sobrantes
    - recorta al limite indicado
    """
    resumen = str(resumen_actual or "").strip()
    marca = str(marca or "").strip()

    if not marca:
        return resumen[:limite]

    if marca in resumen:
        return resumen[:limite]

    return f"{resumen} | {marca}".strip(" |")[:limite]

def decidir_resultado_ml_sigue_recolectando(ml_cortado):
    """
    Decide si WhatsApp debe frenar porque Mercado Libre sigue recolectando.

    Retorna None si ML esta cortado y el flujo puede continuar.
    """
    if ml_cortado:
        return None

    return {
        "ok": False,
        "motivo": "ml_sigue_recolectando",
    }
