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