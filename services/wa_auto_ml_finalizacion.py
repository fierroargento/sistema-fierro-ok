def finalizar_wa_auto_ml_ok(
    pedido,
    resumen,
    marca,
    tel,
    accion,
    detalle_extra,
    motivo,
    now_fn,
    agregar_marca_a_resumen_fn,
    limpiar_pendientes_fn,
    db_session,
    registrar_auditoria_fn,
    construir_detalle_auditoria_fn,
    construir_log_error_auditoria_fn,
    construir_log_ok_fn,
    decidir_resultado_final_fn,
    print_fn=print,
):
    """
    Finaliza el handoff exitoso de ML a WhatsApp.

    Centraliza efectos operativos del tramo OK:
    - actualiza ultimo contacto WA
    - actualiza resumen
    - limpia pendientes ML
    - commitea
    - audita
    - loguea OK
    - devuelve resultado historico del flujo
    """
    pedido.wa_ultimo_contacto = now_fn()

    pedido.ia_resumen = agregar_marca_a_resumen_fn(
        resumen,
        marca,
        limite=1000,
    )

    limpiar_pendientes_fn(pedido)
    db_session.commit()

    try:
        registrar_auditoria_fn(
            accion=accion,
            entidad="pedido",
            entidad_id=str(pedido.id),
            detalle=construir_detalle_auditoria_fn(
                tel,
                detalle_extra,
                motivo,
            ),
        )
    except Exception as audit_error:
        print_fn(
            construir_log_error_auditoria_fn(
                getattr(pedido, "id", ""),
                audit_error,
            )
        )

    print_fn(
        construir_log_ok_fn(
            getattr(pedido, "id", ""),
            accion,
            detalle_extra,
        )
    )

    return decidir_resultado_final_fn(True)
