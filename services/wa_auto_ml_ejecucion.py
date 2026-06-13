def ejecutar_flujo_wa_desde_ml(
    pedido,
    faltantes_limpios,
    decision_flujo_wa,
    wa_iniciar_desde_ml_fn,
    wa_cerrar_datos_completos_fn,
    cross_sell_post_datos_completos_fn,
    intentar_cross_sell_fn,
    construir_log_error_cross_sell_fn,
):
    """
    Ejecuta el flujo WA correspondiente luego del handoff desde ML.

    Si hay faltantes, inicia flujo de recoleccion.
    Si no hay faltantes, cierra datos completos y dispara cross-sell no bloqueante.
    """
    if faltantes_limpios:
        ok = wa_iniciar_desde_ml_fn(pedido)
    else:
        ok = wa_cerrar_datos_completos_fn(pedido)

        cross_sell_post_datos_completos_fn(
            pedido=pedido,
            ok=ok,
            intentar_cross_sell_fn=intentar_cross_sell_fn,
            construir_log_error_fn=construir_log_error_cross_sell_fn,
        )

    return {
        "ok": ok,
        "accion": decision_flujo_wa["accion"],
        "detalle_extra": decision_flujo_wa["detalle_extra"],
    }
