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

def ia_escalar_si_timeout_operativo_service(
    pedido,
    actualizar_estado_conversacional_fn,
    registrar_evento_operativo_fn,
    db_session,
    segundos_operativos_fn,
    ahora_fn,
    timeout_segundos,
    canal="",
    motivo="Sin respuesta del comprador",
):
    """Escala tras superar el timeout operativo."""
    if not pedido or not getattr(
        pedido,
        "ia_esperando_respuesta",
        False,
    ):
        return False

    ultimo_bot = getattr(
        pedido,
        "ia_ultimo_mensaje_bot",
        None,
    )
    if not ultimo_bot:
        return False

    if (
        segundos_operativos_fn(
            ultimo_bot,
            ahora_fn(),
        )
        < timeout_segundos
    ):
        return False

    if getattr(
        pedido,
        "ia_requiere_operador",
        False,
    ):
        return False

    try:
        pedido.ia_requiere_operador = True
        pedido.ml_mensajes_pendientes = True
        pedido.ml_mensajes_pendientes_count = max(
            int(
                pedido.ml_mensajes_pendientes_count
                or 0
            ),
            1,
        )
        pedido.ia_ultimo_timeout_operador = ahora_fn()

        canal_txt = str(
            canal
            or getattr(
                pedido,
                "ia_canal_activo",
                "",
            )
            or "bot"
        )

        resumen = (
            pedido.ia_resumen
            or ""
        ).strip()

        marca = (
            "BOT: sin respuesta del comprador "
            f"tras 2 hs operativas ({canal_txt})"
        )

        if marca not in resumen:
            pedido.ia_resumen = (
                f"{resumen} | {marca}"
            ).strip(" |")[:1000]

        canal_timeout = str(
            canal_txt or ""
        ).strip().lower()
        es_timeout_wa = canal_timeout in (
            "whatsapp",
            "wa",
        )

        if es_timeout_wa:
            try:
                pedido.wa_estado = "requiere_operador"
            except Exception:
                pass

            actualizar_estado_conversacional_fn(
                pedido,
                owner_actual="operador",
                canal_activo=canal_txt,
                estado_conversacional=(
                    "takeover_operador"
                ),
                takeover_activo=True,
                bot_pausado=True,
            )

            evento_owner = "operador"
            evento_estado_conversacional = (
                "takeover_operador"
            )

        else:
            evento_owner = "operador"
            evento_estado_conversacional = (
                "pendiente_operador_ml"
            )

        registrar_evento_operativo_fn(
            pedido=pedido,
            tipo_evento="timeout_respuesta_cliente",
            origen="scheduler",
            canal=canal_txt,
            owner=evento_owner,
            estado_conversacional=(
                evento_estado_conversacional
            ),
            payload={
                "motivo": motivo,
                "canal": canal_txt,
                "ia_esperando_respuesta": (
                    pedido.ia_esperando_respuesta
                ),
                "ia_ultimo_mensaje_bot": str(
                    ultimo_bot
                ),
            },
            resultado="escalado_operador",
            detalle=marca,
            procesado=True,
        )

        db_session.commit()

        print(
            f"[IA-APB] Pedido #{pedido.id} "
            "escalado por timeout operativo "
            f"canal={canal_txt}"
        )
        return True

    except Exception as e:
        try:
            db_session.rollback()
        except Exception:
            pass

        print(
            "[IA-APB] Error escalando por timeout:",
            e,
        )
        return False
