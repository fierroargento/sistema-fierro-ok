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


from types import SimpleNamespace as _SimpleNamespace

from services.ml_importacion import (
    ml_aplicar_datos_envio_service as _ml_aplicar_datos_envio_service,
)


def _pedido_ml_envio_fake():
    return _SimpleNamespace(
        ml_shipping_id="",
        ml_logistic_type="",
        ml_shipping_mode="",
        ml_tipo="",
        tipo_entrega="",
        seguimiento="",
        empresa_envio="",
        direccion="",
        codigo_postal="",
        localidad="",
        provincia="",
        sucursal_nombre="",
        ml_shipping_status="",
        etiqueta_archivo="",
    )


def test_ml_aplicar_datos_envio_service_completa_mercado_envios_y_etiqueta():
    pedido = _pedido_ml_envio_fake()

    order = {
        "shipping": {
            "id": "SHIP_ORDER",
            "logistic_type": "drop_off",
            "mode": "me2",
            "status": "ready",
        }
    }
    shipment = {
        "id": "SHIP_SHIPMENT",
        "status": "shipped",
        "tracking_number": "TRACK123",
        "receiver_address": {
            "address_line": "Calle 123",
            "zip_code": "1000",
            "city": {"name": "CABA"},
            "state": {"name": "Buenos Aires"},
        },
    }

    defaults_aplicados = []

    resultado = _ml_aplicar_datos_envio_service(
        pedido,
        order,
        shipment,
        ml_mapear_tipo_fn=lambda order, shipment: "Mercado Envíos",
        ml_mapear_tipo_entrega_fn=lambda order, shipment: "Domicilio",
        aplicar_default_tipo_entrega_fn=lambda pedido: defaults_aplicados.append(pedido),
        es_ml_acordas_via_cargo_fn=lambda pedido: False,
        etiqueta_archivo_local_disponible_fn=lambda archivo: False,
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: f"ml_{shipping_id}.pdf",
    )

    assert resultado is pedido
    assert pedido.ml_shipping_id == "SHIP_ORDER"
    assert pedido.ml_logistic_type == "drop_off"
    assert pedido.ml_shipping_mode == "me2"
    assert pedido.ml_tipo == "Mercado Envíos"
    assert pedido.tipo_entrega == "Domicilio"
    assert pedido.empresa_envio == "Mercado Envíos"
    assert pedido.seguimiento == "TRACK123"
    assert pedido.direccion == "Calle 123"
    assert pedido.codigo_postal == "1000"
    assert pedido.localidad == "CABA"
    assert pedido.provincia == "Buenos Aires"
    assert pedido.ml_shipping_status == "shipped"
    assert pedido.etiqueta_archivo == "ml_SHIP_ORDER.pdf"
    assert defaults_aplicados == [pedido]


def test_ml_aplicar_datos_envio_service_acordas_via_cargo_con_sucursal_fuerza_tipo_sucursal():
    pedido = _pedido_ml_envio_fake()
    pedido.empresa_envio = "Via Cargo"

    order = {"shipping": {"id": "SHIP1"}}
    shipment = {
        "receiver_address": {
            "agency_name": "Sucursal Centro",
            "city": {"name": "Viedma"},
            "state": {"name": "Rio Negro"},
        }
    }

    _ml_aplicar_datos_envio_service(
        pedido,
        order,
        shipment,
        ml_mapear_tipo_fn=lambda order, shipment: "Acordas la Entrega",
        ml_mapear_tipo_entrega_fn=lambda order, shipment: "Domicilio",
        aplicar_default_tipo_entrega_fn=lambda pedido: None,
        es_ml_acordas_via_cargo_fn=lambda pedido: True,
        etiqueta_archivo_local_disponible_fn=lambda archivo: True,
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: None,
    )

    assert pedido.sucursal_nombre == "Sucursal Centro"
    assert pedido.tipo_entrega == "Sucursal"
    assert pedido.localidad == "Viedma"
    assert pedido.provincia == "Rio Negro"

