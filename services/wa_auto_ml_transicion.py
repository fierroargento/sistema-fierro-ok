def intentar_avisar_transicion_ml_wa(
    pedido,
    resumen_actual,
    debe_avisar_fn,
    texto_transicion_fn,
    puede_enviar_mensaje_fn,
    enviar_mensaje_ml_fn,
    registrar_envio_automatico_fn,
    marcar_transicion_resumen_fn,
    construir_log_bloqueado_fn,
    construir_log_error_fn,
    print_fn=print,
):
    """
    Intenta avisar por Mercado Libre que el canal operativo pasa a WhatsApp.

    No hace commit ni rollback.
    Devuelve el resumen que debe continuar usando el flujo.
    """
    resumen = resumen_actual

    if not debe_avisar_fn(pedido):
        return resumen

    try:
        texto_transicion_ml = texto_transicion_fn()

        permitido, motivo = puede_enviar_mensaje_fn(
            pedido=pedido,
            canal="ml",
            texto=texto_transicion_ml,
        )

        if not permitido:
            print_fn(
                construir_log_bloqueado_fn(
                    getattr(pedido, "id", ""),
                    motivo,
                )
            )
            return resumen

        enviar_mensaje_ml_fn(
            pedido,
            texto_transicion_ml,
        )

        registrar_envio_automatico_fn(
            pedido=pedido,
            canal="ml",
            texto=texto_transicion_ml,
        )

        return marcar_transicion_resumen_fn(pedido)

    except Exception as e:
        print_fn(
            construir_log_error_fn(
                getattr(pedido, "id", ""),
                e,
            )
        )
        return resumen
