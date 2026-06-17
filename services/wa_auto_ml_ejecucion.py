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
    Ejecuta el primer paso del handoff ML -> WhatsApp.

    APB:
    - Al iniciar WA desde ML, el primer mensaje solo abre el canal.
    - No se encadenan mensajes de cierre, despacho ni cross-sell.
    - El bot debe esperar una respuesta real del cliente por WhatsApp para
      confirmar que la ventana quedo abierta.
    """
    ok = wa_iniciar_desde_ml_fn(pedido)

    return {
        "ok": ok,
        "accion": decision_flujo_wa["accion"],
        "detalle_extra": decision_flujo_wa["detalle_extra"],
        "espera_respuesta_cliente_wa": True,
    }
