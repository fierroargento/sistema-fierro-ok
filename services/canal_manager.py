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

from datetime import datetime, timedelta


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
        ahora = datetime.utcnow()

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
            datetime.utcnow()
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