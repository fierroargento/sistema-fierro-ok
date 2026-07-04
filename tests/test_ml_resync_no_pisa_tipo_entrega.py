from types import SimpleNamespace

from services.ml_importacion import ml_aplicar_datos_envio_service


def _pedido_base(**kwargs):
    data = dict(
        ml_shipping_id="",
        ml_logistic_type="",
        ml_shipping_mode="",
        ml_shipping_status="",
        ml_tipo="Acordás la Entrega",
        empresa_envio="",
        tipo_entrega="",
        direccion="",
        codigo_postal="",
        localidad="",
        provincia="",
        sucursal_nombre="",
        correo_sucursales_ofrecidas=None,
        ia_sucursales_ofrecidas=None,
        etiqueta_archivo="",
        seguimiento="",
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def _order_shipment():
    order = {
        "shipping": {
            "id": "SHIP123",
            "logistic_type": "custom",
            "mode": "custom",
        }
    }

    shipment = {
        "id": "SHIP123",
        "receiver_address": {
            "address_line": "Calle Sosa del Valle 3255",
            "zip_code": "1879",
            "city": {"name": "Quilmes Oeste"},
            "state": {"name": "Buenos Aires"},
        },
    }

    return order, shipment


def _aplicar(pedido, tipo_entrega_ml="Domicilio"):
    order, shipment = _order_shipment()

    return ml_aplicar_datos_envio_service(
        pedido,
        order,
        shipment,
        ml_mapear_tipo_fn=lambda order, shipment: "Acordás la Entrega",
        ml_mapear_tipo_entrega_fn=lambda order, shipment: tipo_entrega_ml,
        aplicar_default_tipo_entrega_fn=lambda pedido: None,
        es_ml_acordas_via_cargo_fn=lambda pedido: False,
        etiqueta_archivo_local_disponible_fn=lambda archivo: False,
        ml_guardar_etiqueta_pdf_fn=lambda shipping_id: "",
    )


def test_resync_ml_no_pisa_sucursal_correo_si_hay_sucursales_ofrecidas():
    pedido = _pedido_base(
        empresa_envio="Correo Argentino",
        tipo_entrega="Domicilio",
        correo_sucursales_ofrecidas='[{"nombre": "Sucursal Correo"}]',
    )

    _aplicar(pedido, tipo_entrega_ml="Domicilio")

    assert pedido.tipo_entrega == "Sucursal"


def test_resync_ml_preserva_tipo_entrega_interno_acordas_con_transporte():
    pedido = _pedido_base(
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
    )

    _aplicar(pedido, tipo_entrega_ml="Domicilio")

    assert pedido.tipo_entrega == "Sucursal"


def test_resync_ml_aplica_tipo_ml_si_no_hay_decision_interna():
    pedido = _pedido_base(
        empresa_envio="",
        tipo_entrega="",
    )

    _aplicar(pedido, tipo_entrega_ml="Domicilio")

    assert pedido.tipo_entrega == "Domicilio"
