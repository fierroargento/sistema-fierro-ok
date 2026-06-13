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

def decidir_flujo_wa_desde_ml(faltantes_limpios):
    """
    Decide que flujo de WhatsApp corresponde luego del disparo desde ML.

    - Si hay faltantes: WhatsApp debe continuar la recoleccion.
    - Si no hay faltantes: WhatsApp debe cerrar datos completos.
    """
    faltantes = []

    for campo in (faltantes_limpios or []):
        campo = str(campo or "").strip()
        if campo:
            faltantes.append(campo)

    if faltantes:
        return {
            "flujo": "faltantes",
            "accion": "Inició WhatsApp desde ML",
            "detalle_extra": "handoff ML→WA con ML cortado | " + ", ".join(faltantes),
        }

    return {
        "flujo": "datos_completos",
        "accion": "Inició WhatsApp con datos completos",
        "detalle_extra": "datos completos | cross-sell evaluado post handoff ML",
    }

def marca_wa_iniciado_desde_ml():
    """
    Marca historica usada en el resumen cuando WhatsApp inicia automaticamente desde ML.
    """
    return "WA iniciado automáticamente desde ML"

def limpiar_pendientes_ml_post_handoff(pedido):
    """
    Limpia flags de mensajes pendientes ML luego de iniciar WhatsApp desde ML.

    No escribe DB.
    No hace commit.
    Solo muta el objeto pedido en memoria.
    """
    try:
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0
        return True
    except Exception:
        return False

def construir_detalle_auditoria_wa_desde_ml(tel, detalle_extra, motivo):
    """
    Construye el detalle historico de auditoria para el handoff ML -> WA.
    """
    tel = str(tel or "").strip()
    detalle_extra = str(detalle_extra or "").strip()
    motivo = str(motivo or "").strip()

    return f"Origen ML/Acordás. Teléfono: {tel}. {detalle_extra}. Motivo: {motivo}"

def decidir_resultado_final_wa_desde_ml(ok):
    """
    Decide el resultado final historico del disparo automatico WA desde ML.
    """
    if ok:
        return True, "enviado"

    return False, "wa_no_enviado"

def decidir_resultado_ml_debe_cerrar_sucursal(bloqueado):
    """
    Decide si el flujo WA debe frenarse porque ML/Acordás debe cerrar sucursal primero.

    Retorna None si no hay bloqueo.
    """
    if not bloqueado:
        return None

    return {
        "ok": False,
        "motivo": "ml_debe_cerrar_sucursal",
    }

def decidir_resultado_error_wa_desde_ml(error):
    """
    Decide el resultado historico ante error general del disparo WA desde ML.
    """
    return False, str(error)

def construir_log_ml_sigue_recolectando(pedido_id, faltantes_limpios):
    """
    Construye el log historico cuando ML sigue recolectando y WA no debe iniciar.
    """
    faltantes = ", ".join(faltantes_limpios or [])
    return f"[WA-AUTO-ML] NO inicia WA pedido #{pedido_id}: ML activo sigue recolectando ({faltantes})"


def construir_log_ml_debe_cerrar_sucursal(pedido_id):
    """
    Construye el log historico cuando ML/Acordas debe cerrar sucursal primero.
    """
    return (
        f"[WA-AUTO-ML] No se inicia WhatsApp pedido #{pedido_id}: "
        "ML debe cerrar sucursal primero."
    )


def construir_log_wa_auto_ml_ok(pedido_id, accion, detalle_extra):
    """
    Construye el log historico de exito del inicio automatico WA desde ML.
    """
    return f"[WA-AUTO-ML] OK pedido #{pedido_id}: {accion} ({detalle_extra})"


def construir_log_error_wa_auto_ml(pedido_id, error):
    """
    Construye el log historico de error general del inicio automatico WA desde ML.
    """
    return f"[WA-AUTO-ML] Error pedido #{pedido_id}: {error}"

def construir_log_error_cross_sell_wa_auto_ml(error):
    """
    Construye el log historico cuando falla el intento de cross sell automatico.
    """
    return f"[WA-AUTO-ML] Error intentando cross sell automático: {error}"


def construir_log_canal_manager_ml_bloqueado(pedido_id, motivo):
    """
    Construye el log historico cuando Canal Manager bloquea el mensaje ML.
    """
    return f"[CANAL-MANAGER] ML bloqueado pedido #{pedido_id}: {motivo}"


def construir_log_error_aviso_migracion_ml_wa(pedido_id, error):
    """
    Construye el log historico cuando falla el aviso de migracion ML a WA.
    """
    return f"[WA-AUTO-ML] No se pudo avisar migración por ML pedido #{pedido_id}: {error}"


def construir_log_error_auditoria_wa_auto_ml(pedido_id, error):
    """
    Construye el log historico cuando falla la auditoria del inicio WA desde ML.
    """
    return f"[WA-AUTO-ML] No se pudo auditar pedido #{pedido_id}: {error}"
