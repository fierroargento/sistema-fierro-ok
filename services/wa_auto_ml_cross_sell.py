def intentar_cross_sell_post_datos_completos(
    pedido,
    ok,
    intentar_cross_sell_fn,
    construir_log_error_fn,
    print_fn=print,
):
    """
    Intenta disparar cross-sell automatico despues de cerrar datos completos WA.

    Devuelve True solo si el cross-sell realmente inicio.
    No alcanza con que la funcion no explote: respeta el resultado devuelto por
    intentar_cross_sell_fn.
    """
    if not ok:
        return False

    try:
        resultado = intentar_cross_sell_fn(
            pedido,
            origen_disparo="ml_datos_completos",
        )

        if isinstance(resultado, tuple):
            return bool(resultado[0])

        return bool(resultado)

    except Exception as e:
        print_fn(construir_log_error_fn(e))
        return False
