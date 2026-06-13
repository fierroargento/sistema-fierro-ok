def manejar_ml_sigue_recolectando_si_corresponde(
    pedido,
    faltantes_limpios,
    decision_ml_sigue,
    db_session,
    construir_marca_fn,
    agregar_marca_resumen_fn,
    construir_log_fn,
    print_fn=print,
):
    """
    Maneja el caso donde ML sigue activo recolectando datos y WA no debe iniciar.

    Devuelve None si no corresponde frenar.
    Devuelve (ok, motivo) si corresponde frenar el inicio WA.
    """
    if not decision_ml_sigue:
        return None

    try:
        resumen = (getattr(pedido, "ia_resumen", "") or "").strip()
        marca = construir_marca_fn(faltantes_limpios)

        pedido.ia_resumen = agregar_marca_resumen_fn(
            resumen,
            marca,
            limite=1000,
        )
        db_session.commit()
    except Exception:
        try:
            db_session.rollback()
        except Exception:
            pass

    print_fn(
        construir_log_fn(
            getattr(pedido, "id", ""),
            faltantes_limpios,
        )
    )

    return decision_ml_sigue["ok"], decision_ml_sigue["motivo"]
