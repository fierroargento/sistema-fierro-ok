from domain.estados import Estado
from services.pedidos_estado import es_via_cargo


def aplicar_autoavance_post_despacho_service(pedido):
    if pedido.estado != Estado.DESPACHADO:
        return

    if es_via_cargo(pedido.empresa_envio):
        if pedido.seguimiento:
            pedido.estado = Estado.VERIFICAR_DESTINO
        return

    if (
        pedido.canal == "Mercado Libre"
        and pedido.ml_tipo == "Acordás la Entrega"
        and pedido.empresa_envio in ["Andreani", "Correo Argentino"]
        and pedido.seguimiento
    ):
        pedido.estado = Estado.VERIFICAR_DESTINO

def actualizar_estado_automatico_service(
    pedido,
    puede_imprimir_etiqueta_directamente,
    puede_imprimir_acordas_entrega,
    debe_pasar_a_demora_entrega,
):
    if pedido.estado == Estado.CARGANDO and (
        puede_imprimir_etiqueta_directamente(pedido)
        or puede_imprimir_acordas_entrega(pedido)
    ):
        pedido.estado = Estado.ETIQUETA_LISTA
        return

    if debe_pasar_a_demora_entrega(pedido):
        pedido.estado = Estado.DEMORA


def actualizar_estado_automatico_protegido_service(
    pedido,
    puede_imprimir_etiqueta_directamente,
    puede_imprimir_acordas_entrega,
    debe_pasar_a_demora_entrega,
    *,
    evento_operativo_model,
    evaluar_bloqueo_fn=None,
    aplicar_reversion_fn=None,
    cross_sell_rule_fn=None,
    auto_enabled=None,
    manual_enabled=None,
    log_fn=print,
):
    """
    Ejecuta el autoavance y conserva la protección
    comercial de cross-sell previa a Etiqueta Lista.
    """
    estado_anterior = getattr(pedido, "estado", None)

    def log_error_cross_sell(error):
        log_fn(
            "[CROSS-SELL-APB] Error evaluando "
            f"bloqueo de autoavance: {error}"
        )

    try:
        if evaluar_bloqueo_fn is None:
            from services.ml_sucursal_cross_sell_guard import (
                debe_bloquear_autoavance_etiqueta_lista_por_cross_sell,
            )

            evaluar_bloqueo_fn = (
                debe_bloquear_autoavance_etiqueta_lista_por_cross_sell
            )

        if cross_sell_rule_fn is None:
            from services.cross_sell_rules import (
                debe_bloquear_etiqueta_lista_por_cross_sell,
            )

            cross_sell_rule_fn = (
                debe_bloquear_etiqueta_lista_por_cross_sell
            )

        if auto_enabled is None or manual_enabled is None:
            from modules.whatsapp.config import (
                CROSS_SELL_AUTO_ENABLED,
                CROSS_SELL_MANUAL_ENABLED,
            )

            if auto_enabled is None:
                auto_enabled = CROSS_SELL_AUTO_ENABLED
            if manual_enabled is None:
                manual_enabled = CROSS_SELL_MANUAL_ENABLED

        bloquear_cross_sell = evaluar_bloqueo_fn(
            pedido,
            estado_cargando=Estado.CARGANDO,
            cross_sell_rule_fn=cross_sell_rule_fn,
            auto_enabled=auto_enabled,
            manual_enabled=manual_enabled,
            evento_operativo_model=evento_operativo_model,
            log_error_fn=log_error_cross_sell,
        )

    except Exception as error:
        log_fn(
            "[CROSS-SELL-APB] Error preparando "
            f"bloqueo de autoavance: {error}"
        )
        bloquear_cross_sell = False

    actualizar_estado_automatico_service(
        pedido,
        puede_imprimir_etiqueta_directamente,
        puede_imprimir_acordas_entrega,
        debe_pasar_a_demora_entrega,
    )

    if aplicar_reversion_fn is None:
        from services.ml_sucursal_cross_sell_guard import (
            aplicar_reversion_autoavance_si_corresponde,
        )

        aplicar_reversion_fn = (
            aplicar_reversion_autoavance_si_corresponde
        )

    aplicar_reversion_fn(
        pedido,
        estado_anterior=estado_anterior,
        estado_etiqueta_lista=Estado.ETIQUETA_LISTA,
        bloquear_cross_sell=bloquear_cross_sell,
    )
