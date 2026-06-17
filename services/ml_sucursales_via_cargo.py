"""
services/ml_sucursales_via_cargo.py
────────────────────────────────────
Regla APB:
Antes de pasar de Mercado Libre a WhatsApp, ML/Acordás/Vía Cargo debe
intentar cerrar la sucursal por el canal original mientras ML siga activo.
"""

from datetime import datetime


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
    Devuelve:
    - None: no interviene y el flujo puede continuar.
    - dict: resultado final para cortar el flujo antes de WhatsApp.

    APB:
    Si ML sigue activo y falta sucursal, primero se ofrece sucursal por ML.
    Si ML está cortado, WhatsApp puede tomar la posta para destrabar logística.
    """
    if ml_cortado:
        return None

    now_fn = now_fn or datetime.utcnow

    mensaje = sugerir_sucursales_fn(pedido)

    if not mensaje:
        return {
            "ok": False,
            "motivo": "ml_debe_cerrar_sucursal",
        }

    try:
        permitido, motivo = puede_enviar_mensaje_fn(
            pedido=pedido,
            canal="ml",
            texto=mensaje,
        )

        if not permitido:
            return {
                "ok": False,
                "motivo": motivo,
            }

        enviar_mensaje_ml_fn(pedido, mensaje)

        registrar_envio_automatico_fn(
            pedido=pedido,
            canal="ml",
            texto=mensaje,
        )

        pedido.ia_respuesta_sugerida = mensaje
        pedido.ia_respuesta_enviada_hash = ia_hash_texto_fn(mensaje)
        pedido.ia_ultima_respuesta_enviada = now_fn()
        pedido.ml_mensajes_pendientes = False
        pedido.ml_mensajes_pendientes_count = 0

        db_session.commit()

        return {
            "ok": True,
            "motivo": "sucursales_ml_enviadas_antes_wa",
        }

    except Exception:
        try:
            db_session.rollback()
        except Exception:
            pass

        return {
            "ok": False,
            "motivo": "error_sucursales_ml_antes_wa",
        }
