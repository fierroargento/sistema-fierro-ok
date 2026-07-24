import hashlib

from services.fechas import ahora_utc_naive


def ia_hash_texto_service(texto):
    return hashlib.sha256(
        str(texto or "").encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()


def ia_marcar_mensaje_bot_service(
    pedido,
    canal,
    actualizar_estado_conversacional_fn,
    registrar_evento_operativo_fn,
    db_session,
    texto=None,
    commit=True,
    ahora_fn=ahora_utc_naive,
    hash_texto_fn=ia_hash_texto_service,
):
    """Registra que el bot habló y espera respuesta."""
    if not pedido:
        return False

    try:
        pedido.ia_esperando_respuesta = True
        pedido.ia_ultimo_mensaje_bot = ahora_fn()
        pedido.ia_canal_activo = (
            str(canal or "").strip()[:30]
            or None
        )

        if texto:
            pedido.ia_respuesta_enviada_hash = (
                hash_texto_fn(texto)
            )
            pedido.ia_ultima_respuesta_enviada = (
                pedido.ia_ultimo_mensaje_bot
            )

        actualizar_estado_conversacional_fn(
            pedido,
            owner_actual="bot",
            canal_activo=(
                pedido.ia_canal_activo
                or canal
            ),
            estado_conversacional="esperando_respuesta",
            takeover_activo=False,
            bot_pausado=False,
            ultimo_mensaje_bot=(
                pedido.ia_ultimo_mensaje_bot
            ),
        )

        registrar_evento_operativo_fn(
            pedido=pedido,
            tipo_evento="bot_esperando_respuesta",
            origen="bot",
            canal=(
                pedido.ia_canal_activo
                or canal
                or "sistema"
            ),
            owner="bot",
            estado_conversacional="esperando_respuesta",
            payload={
                "canal": pedido.ia_canal_activo,
                "ia_esperando_respuesta": (
                    pedido.ia_esperando_respuesta
                ),
            },
            resultado="ok",
            detalle=(texto or "")[:500],
            procesado=True,
        )

        if commit:
            db_session.commit()

        return True

    except Exception as e:
        try:
            db_session.rollback()
        except Exception:
            pass

        print(
            "[IA-APB] No se pudo marcar mensaje bot:",
            e,
        )
        return False
