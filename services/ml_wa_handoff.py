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

def _obtener_estado_conversacional_para_handoff(
    pedido,
    obtener_estado_conversacional_fn=None,
):
    if not callable(obtener_estado_conversacional_fn):
        return None

    try:
        return obtener_estado_conversacional_fn(
            pedido,
            crear_si_no_existe=False,
        )

    except TypeError:
        try:
            return obtener_estado_conversacional_fn(pedido)
        except Exception:
            return None

    except Exception:
        return None


def ml_conversacion_cortada_para_handoff_wa_service(
    pedido,
    motivo_handoff="",
    obtener_estado_conversacional_fn=None,
):
    """Check APB para permitir ML -> WhatsApp con datos faltantes.

    WhatsApp puede continuar la recoleccion con faltantes solo si Mercado Libre
    dejo de ser un canal util o seguro. Si ML esta activo y el cliente viene
    respondiendo, la recoleccion debe seguir por ML.

    APB / SaaS:
    - No envia mensajes.
    - No escribe DB.
    - No depende de app.py.
    - Recibe obtener_estado_conversacional_fn desde la capa orquestadora.
    """
    if not pedido:
        return False, "sin_pedido"

    if getattr(pedido, "ia_ultimo_timeout_operador", None):
        return True, "timeout_ml_registrado"

    if getattr(pedido, "ia_requiere_operador", False):
        return True, "requiere_operador"

    canal_ia = str(getattr(pedido, "ia_canal_activo", "") or "").strip().lower()
    if canal_ia and canal_ia not in ["ml", "mercadolibre", "mercado_libre"]:
        return True, f"canal_ia_no_ml:{canal_ia}"

    estado_conv = _obtener_estado_conversacional_para_handoff(
        pedido,
        obtener_estado_conversacional_fn=obtener_estado_conversacional_fn,
    )

    if estado_conv:
        canal_conv = str(
            getattr(estado_conv, "canal_activo", "") or ""
        ).strip().lower()

        if canal_conv and canal_conv not in ["ml", "mercadolibre", "mercado_libre"]:
            return True, f"canal_conversacional_no_ml:{canal_conv}"

        if getattr(estado_conv, "bot_pausado", False):
            return True, "bot_pausado"

        if getattr(estado_conv, "takeover_activo", False):
            return True, "takeover_operador"

    motivo_txt = str(motivo_handoff or "").strip().lower()
    motivos_corte = [
        "timeout",
        "bloqueado",
        "blocked",
        "rechazado",
        "fallo_ml",
        "error_ml",
        "ml_no_disponible",
        "canal_no_disponible",
    ]

    if motivo_txt and any(m in motivo_txt for m in motivos_corte):
        return True, f"motivo_handoff:{motivo_handoff}"

    return False, "ml_activo_sigue_recolectando"
