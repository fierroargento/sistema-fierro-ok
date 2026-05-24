"""
services/canal_manager.py
─────────────────────────
Autoridad APB mínima para mensajes automáticos.

Objetivo:
- evitar spam,
- evitar loops,
- evitar duplicados,
- respetar ownership de canal,
- centralizar reglas mínimas de envío.
"""

from datetime import datetime, timedelta, UTC

from domain.estados import Estado, ESTADOS_CERRADOS

# Cooldown anti-spam por defecto
COOLDOWN_MINUTOS = 30


def puede_enviar_mensaje(
    pedido,
    canal,
    texto,
):
    """
    Decide si un mensaje automático puede enviarse.

    Retorna:
    (True, motivo)  -> puede enviar
    (False, motivo) -> bloqueado
    """

    # ---------------------------------------------------
    # REGLA 1
    # WhatsApp tiene autoridad sobre ML
    # ---------------------------------------------------

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip().lower()

    if canal == "ml" and wa_estado:
        return (
            False,
            f"WhatsApp activo ({wa_estado})"
        )

    # ---------------------------------------------------
    # REGLA 2
    # Anti-duplicación exacta
    # ---------------------------------------------------

    ultimo_texto = str(
        getattr(
            pedido,
            "ultimo_mensaje_automatico_texto",
            ""
        ) or ""
    ).strip()

    ultimo_canal = str(
        getattr(
            pedido,
            "ultimo_mensaje_automatico_canal",
            ""
        ) or ""
    ).strip().lower()

    if (
        ultimo_texto
        and ultimo_canal == canal
        and ultimo_texto == texto.strip()
    ):
        return (
            False,
            "Mensaje automático repetido"
        )

    # ---------------------------------------------------
    # REGLA 3
    # Cooldown anti-spam
    # ---------------------------------------------------

    fecha_ultimo = getattr(
        pedido,
        "ultimo_mensaje_automatico_fecha",
        None
    )

    if (
        fecha_ultimo
        and ultimo_canal == canal
    ):
        ahora = datetime.now(UTC)

        diferencia = (
            ahora - fecha_ultimo
        )

        if diferencia < timedelta(
            minutes=COOLDOWN_MINUTOS
        ):
            return (
                False,
                f"Cooldown activo ({COOLDOWN_MINUTOS} min)"
            )

    return (
        True,
        "OK"
    )


def registrar_envio_automatico(
    pedido,
    canal,
    texto,
):
    """
    Guarda metadata del último mensaje automático.
    """

    try:
        pedido.ultimo_mensaje_automatico_texto = texto

        pedido.ultimo_mensaje_automatico_canal = canal

        pedido.ultimo_mensaje_automatico_fecha = (
            datetime.now(UTC)
        )

    except Exception as e:
        print(
            "[CANAL-MANAGER] Error registrando envío:",
            e
        )

def wa_puede_gobernar_timeout(pedido):
    """
    Devuelve True solo si WhatsApp
    es realmente el owner operativo
    del timeout del pedido.
    """

    canal = str(
        getattr(pedido, "ia_canal_activo", "") or ""
    ).strip().lower()

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip()

    # APB:
    # Si el canal activo no es WhatsApp,
    # WA no gobierna.
    if canal not in ("whatsapp", "wa"):
        return False

    # APB:
    # Debe existir estado WA real.
    if not wa_estado:
        return False

    return True  

def ml_puede_gobernar_timeout(pedido):
    """
    Devuelve True solo si Mercado Libre
    puede gobernar el timeout del pedido.

    APB:
    si WhatsApp ya tomó ownership,
    ML queda pasivo.
    """

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip()

    if wa_estado:
        return False

    return True

def puede_hacer_handoff_ml_a_whatsapp(
    pedido
):
    """
    Decide si el pedido puede migrar
    automáticamente de ML a WhatsApp.

    Solo evalúa ownership/reglas APB.
    No ejecuta mensajes ni acciones.
    """

    if not pedido:
        return (
            False,
            "sin_pedido",
        )

    wa_estado = str(
        getattr(pedido, "wa_estado", "") or ""
    ).strip()

    # APB:
    # Nunca pisar un flujo WA existente.
    if wa_estado:
        return (
            False,
            "wa_ya_iniciado",
        )

    estado = str(
        getattr(pedido, "estado", "") or ""
    ).strip()

    if estado in ESTADOS_CERRADOS + [
        Estado.DESPACHADO,
    ]:
        return (
            False,
            "pedido_cerrado",
        )

    ml_order_status_actual = str(
        getattr(
            pedido,
            "ml_order_status",
            "",
        ) or ""
    ).lower().strip()

    if ml_order_status_actual in {
        "closed",
        "cancelled",
        "invalid",
        "delivered",
    }:
        return (
            False,
            "ml_cerrado",
        )

    return (
        True,
        "ok",
    )      