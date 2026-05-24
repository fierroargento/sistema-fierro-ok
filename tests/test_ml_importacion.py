from services.ml_importacion import (
    ml_prevalidar_importacion_order_service,
)


def test_ml_historico_entregado_no_reimporta():
    order = {
        "id": "3001",
    }

    resultado = (
        ml_prevalidar_importacion_order_service(
            order=order,
            shipment={},
            ml_pedido_esta_ignorado=lambda order_id: False,
            ml_order_esta_entregado=lambda order, shipment: True,
            ml_pedido_existente_operativo=lambda order, shipment: None,
            ml_registrar_order_ignorado=lambda order_id, motivo: None,
            ml_marcar_pedido_finalizado_por_entrega=lambda pedido, order, shipment: pedido,
            ml_order_debe_omitirse=lambda order, shipment: (False, ""),
            ml_borrar_pedido_importado_si_corresponde=lambda pedido: False,
            ml_es_mercado_envios_order=lambda order, shipment: False,
            ml_envio_ya_despachado=lambda order, shipment: False,
            ml_preparar_etiqueta_mercado_envios=lambda order, shipment: "",
        )
    )

    assert resultado["continuar"] is False
    assert "histórico" in resultado["motivo"]


def test_ml_mercado_envios_ya_despachado_no_importa():
    order = {
        "id": "3002",
    }

    resultado = (
        ml_prevalidar_importacion_order_service(
            order=order,
            shipment={},
            ml_pedido_esta_ignorado=lambda order_id: False,
            ml_order_esta_entregado=lambda order, shipment: False,
            ml_pedido_existente_operativo=lambda order, shipment: None,
            ml_registrar_order_ignorado=lambda order_id, motivo: None,
            ml_marcar_pedido_finalizado_por_entrega=lambda pedido, order, shipment: pedido,
            ml_order_debe_omitirse=lambda order, shipment: (False, ""),
            ml_borrar_pedido_importado_si_corresponde=lambda pedido: False,
            ml_es_mercado_envios_order=lambda order, shipment: True,
            ml_envio_ya_despachado=lambda order, shipment: True,
            ml_preparar_etiqueta_mercado_envios=lambda order, shipment: "",
        )
    )

    assert resultado["continuar"] is False
    assert "ya enviado" in resultado["motivo"]


def test_ml_mercado_envios_sin_etiqueta_no_importa():
    order = {
        "id": "3003",
    }

    resultado = (
        ml_prevalidar_importacion_order_service(
            order=order,
            shipment={},
            ml_pedido_esta_ignorado=lambda order_id: False,
            ml_order_esta_entregado=lambda order, shipment: False,
            ml_pedido_existente_operativo=lambda order, shipment: None,
            ml_registrar_order_ignorado=lambda order_id, motivo: None,
            ml_marcar_pedido_finalizado_por_entrega=lambda pedido, order, shipment: pedido,
            ml_order_debe_omitirse=lambda order, shipment: (False, ""),
            ml_borrar_pedido_importado_si_corresponde=lambda pedido: False,
            ml_es_mercado_envios_order=lambda order, shipment: True,
            ml_envio_ya_despachado=lambda order, shipment: False,
            ml_preparar_etiqueta_mercado_envios=lambda order, shipment: "",
        )
    )

    assert resultado["continuar"] is False
    assert "__ML_ME_SIN_ETIQUETA__" in resultado["motivo"]