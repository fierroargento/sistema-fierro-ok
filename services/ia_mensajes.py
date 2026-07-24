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

def ia_marcar_respuesta_cliente_service(
    pedido,
    actualizar_estado_conversacional_fn,
    registrar_evento_operativo_fn,
    db_session,
    canal=None,
    commit=True,
    ahora_fn=ahora_utc_naive,
):
    """Libera la espera cuando el cliente responde."""
    if not pedido:
        return False

    try:
        pedido.ia_esperando_respuesta = False
        pedido.ia_ultimo_mensaje_cliente = ahora_fn()
        canal_respuesta = (
            str(canal or "").strip()[:30]
            or None
        )
        pedido.ia_canal_activo = None

        actualizar_estado_conversacional_fn(
            pedido,
            canal_activo=canal_respuesta,
            estado_conversacional="recolectando_datos",
            ultimo_mensaje_cliente=(
                pedido.ia_ultimo_mensaje_cliente
            ),
        )

        registrar_evento_operativo_fn(
            pedido=pedido,
            tipo_evento="cliente_respondio",
            origen="cliente",
            canal=canal_respuesta or "sistema",
            owner="bot",
            estado_conversacional="recolectando_datos",
            payload={
                "canal": canal_respuesta,
                "ia_esperando_respuesta": (
                    pedido.ia_esperando_respuesta
                ),
            },
            resultado="ok",
            detalle=(
                "El cliente respondió y se liberó "
                "el candado de espera."
            ),
            procesado=True,
        )

        # Si estaba escalado solo por timeout,
        # no se borra ia_requiere_operador.
        if commit:
            db_session.commit()

        return True

    except Exception as e:
        try:
            db_session.rollback()
        except Exception:
            pass

        print(
            "[IA-APB] No se pudo marcar respuesta cliente:",
            e,
        )
        return False

def ia_puede_enviar_automatico_service(
    pedido,
    canal,
    texto=None,
    permitir_requiere_operador=False,
    hash_texto_fn=ia_hash_texto_service,
):
    """Candado global antiacoso para ML y WhatsApp."""
    if not pedido:
        return True, "sin_pedido"

    canal = str(canal or "").strip().lower()
    canal_activo = str(
        getattr(
            pedido,
            "ia_canal_activo",
            "",
        )
        or ""
    ).strip().lower()

    if (
        getattr(
            pedido,
            "ia_requiere_operador",
            False,
        )
        and not permitir_requiere_operador
    ):
        return False, "requiere_operador"

    if getattr(
        pedido,
        "ia_esperando_respuesta",
        False,
    ):
        if canal_activo and canal_activo != canal:
            return False, f"canal_activo_{canal_activo}"

        return False, "esperando_respuesta_cliente"

    if canal_activo and canal_activo != canal:
        return False, f"canal_activo_{canal_activo}"

    if texto:
        texto_hash = hash_texto_fn(texto)
        ultimo_hash = str(
            getattr(
                pedido,
                "ia_respuesta_enviada_hash",
                "",
            )
            or ""
        )
        ultimo_bot = getattr(
            pedido,
            "ia_ultimo_mensaje_bot",
            None,
        )
        ultimo_cliente = getattr(
            pedido,
            "ia_ultimo_mensaje_cliente",
            None,
        )

        if (
            texto_hash == ultimo_hash
            and ultimo_bot
            and (
                not ultimo_cliente
                or ultimo_bot >= ultimo_cliente
            )
        ):
            return (
                False,
                "mensaje_duplicado_sin_respuesta",
            )

    return True, "ok"
