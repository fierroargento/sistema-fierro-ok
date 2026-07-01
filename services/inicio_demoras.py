def actualizar_demoras_inicio_pedidos_service(
    pedidos,
    debe_pasar_a_demora_fn,
    estado_demora,
    commit_fn=None,
    rollback_fn=None,
    commit=True,
    log_prefix="[INICIO-DEMORA]",
):
    """
    Recalcula demoras locales al cargar Inicio.

    No consulta tracking externo ni dispara mensajes. Solo actualiza los pedidos
    cuando la regla local recibida por parametro indica que corresponde demora.
    """
    cambios = 0

    for pedido in pedidos or []:
        try:
            estado_anterior = getattr(pedido, "estado", None)

            if debe_pasar_a_demora_fn(pedido):
                pedido.estado = estado_demora

            if getattr(pedido, "estado", None) != estado_anterior:
                cambios += 1

        except Exception as e:
            print(f"{log_prefix} Error evaluando pedido #{getattr(pedido, 'id', '')}: {e}")

    if cambios and commit and commit_fn:
        try:
            commit_fn()
        except Exception as e:
            if rollback_fn:
                rollback_fn()
            print(f"{log_prefix} Error guardando cambios: {e}")
            return 0

    return cambios
