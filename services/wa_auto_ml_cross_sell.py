def intentar_cross_sell_post_datos_completos(
    pedido,
    ok,
    intentar_cross_sell_fn,
    construir_log_error_fn,
    print_fn=print,
):
    """
    Intenta disparar cross-sell automatico despues de cerrar datos completos WA desde ML.

    No bloquea el flujo principal.
    """
    if not ok:
        return False

    try:
        intentar_cross_sell_fn(
            pedido,
            origen_disparo="ml_datos_completos",
        )
        return True
    except Exception as e:
        print_fn(construir_log_error_fn(e))
        return False
