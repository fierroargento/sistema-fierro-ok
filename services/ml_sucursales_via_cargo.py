"""
Servicios para ofrecer sucursales por Mercado Libre
antes de continuar el flujo logístico o pasar a WhatsApp.
"""

from datetime import datetime


def enviar_sugerencia_sucursales_ml(
    *,
    pedido,
    sugerir_sucursales_fn,
    puede_enviar_mensaje_fn,
    enviar_mensaje_ml_fn,
    registrar_envio_automatico_fn,
    ia_hash_texto_fn,
    db_session,
    motivo_ok,
    motivo_error,
    now_fn=None,
    log_fn=None,
):
    """
    Intenta construir y enviar una sugerencia de
    sucursales por ML.

    Devuelve None si no hay mensaje para ofrecer.
    En los demás casos devuelve un dict estable.
    """
    now_fn = now_fn or datetime.utcnow

    mensaje = sugerir_sucursales_fn(pedido)

    if not mensaje:
        return None

    try:
        permitido, motivo = puede_enviar_mensaje_fn(
            pedido=pedido,
            canal="ml",
            texto=mensaje,
        )

        if not permitido:
            if log_fn:
                log_fn(
                    "[CANAL-MANAGER] ML bloqueado "
                    f"pedido #{getattr(pedido, 'id', '?')}: "
                    f"{motivo}"
                )

            return {
                "ok": False,
                "motivo": motivo,
            }

        enviar_mensaje_ml_fn(
            pedido,
            mensaje,
        )

        registrar_envio_automatico_fn(
            pedido=pedido,
            canal="ml",
            texto=mensaje,
        )

        pedido.ia_respuesta_sugerida = mensaje
        pedido.ia_respuesta_enviada_hash = (
            ia_hash_texto_fn(mensaje)
        )
        pedido.ia_ultima_respuesta_enviada = (
            now_fn()
        )
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0

        db_session.commit()

        return {
            "ok": True,
            "motivo": motivo_ok,
        }

    except Exception as error:
        if log_fn:
            log_fn(
                "[VIA CARGO] No se pudo enviar "
                "sugerencia de sucursales: "
                f"{error}"
            )

        try:
            db_session.rollback()
        except Exception:
            pass

        return {
            "ok": False,
            "motivo": motivo_error,
        }


def intentar_ofrecer_sucursales_ml_antes_wa(
    *,
    pedido,
    ml_cortado,
    sugerir_sucursales_fn,
    puede_enviar_mensaje_fn,
    enviar_mensaje_ml_fn,
    registrar_envio_automatico_fn,
    ia_hash_texto_fn,
    db_session,
    now_fn=None,
):
    """
    Si ML sigue activo, intenta cerrar la sucursal
    antes de permitir el traspaso a WhatsApp.
    """
    if ml_cortado:
        return None

    resultado = enviar_sugerencia_sucursales_ml(
        pedido=pedido,
        sugerir_sucursales_fn=(
            sugerir_sucursales_fn
        ),
        puede_enviar_mensaje_fn=(
            puede_enviar_mensaje_fn
        ),
        enviar_mensaje_ml_fn=(
            enviar_mensaje_ml_fn
        ),
        registrar_envio_automatico_fn=(
            registrar_envio_automatico_fn
        ),
        ia_hash_texto_fn=ia_hash_texto_fn,
        db_session=db_session,
        motivo_ok=(
            "sucursales_ml_enviadas_antes_wa"
        ),
        motivo_error=(
            "error_sucursales_ml_antes_wa"
        ),
        now_fn=now_fn,
    )

    if resultado is None:
        return {
            "ok": False,
            "motivo": "ml_debe_cerrar_sucursal",
        }

    return resultado
