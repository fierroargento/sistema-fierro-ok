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


from services.ml_importacion import (
    ml_aplicar_apb_en_pedido_service as _ml_aplicar_apb_en_pedido_service,
    ml_datos_apb_pedido_service as _ml_datos_apb_pedido_service,
)


def test_ml_datos_apb_pedido_service_detecta_faltantes_acordas():
    pedido = _SimpleNamespace(
        cliente="comprador_123",
        ml_buyer_nickname="comprador_123",
        ml_billing_nombre="",
        dni="",
        ml_billing_documento="",
        telefono="",
    )

    faltantes = _ml_datos_apb_pedido_service(
        pedido,
        es_ml_acordas_entrega_fn=lambda pedido: True,
        parece_nickname_ml_fn=lambda cliente, nickname: cliente == nickname,
        despacho_completo_fn=lambda pedido: False,
    )

    assert faltantes == [
        "nombre real",
        "DNI/CUIT",
        "tel\u00e9fono",
        "datos de entrega",
    ]


def test_ml_datos_apb_pedido_service_no_pide_faltantes_si_no_es_acordas():
    pedido = _SimpleNamespace(
        cliente="comprador_123",
        ml_buyer_nickname="comprador_123",
        ml_billing_nombre="",
        dni="",
        ml_billing_documento="",
        telefono="",
    )

    faltantes = _ml_datos_apb_pedido_service(
        pedido,
        es_ml_acordas_entrega_fn=lambda pedido: False,
        parece_nickname_ml_fn=lambda cliente, nickname: True,
        despacho_completo_fn=lambda pedido: False,
    )

    assert faltantes == []


def _pedido_ml_apb_fake():
    return _SimpleNamespace(
        cliente="comprador_123",
        dni="",
        telefono="",
        ml_buyer_id="",
        ml_buyer_nickname="",
        ml_nombre_real=False,
        ml_datos_fiscales_ok=False,
        ml_billing_nombre="",
        ml_billing_documento="",
        ml_billing_direccion="",
        ml_campos_faltantes="",
        ml_mensaje_contacto="",
    )


def test_ml_aplicar_apb_en_pedido_service_completa_datos_y_mensaje():
    pedido = _pedido_ml_apb_fake()

    order = {
        "buyer": {
            "id": "BUYER1",
            "nickname": "comprador_123",
        }
    }

    resultado = _ml_aplicar_apb_en_pedido_service(
        pedido,
        order,
        shipment={},
        billing_info={"fake": True},
        ml_nombre_cliente_fn=lambda order, shipment: "Juan Perez",
        ml_extraer_nombre_billing_fn=lambda billing_info: "Juan Fiscal",
        ml_extraer_documento_billing_fn=lambda billing_info: "20123456789",
        ml_extraer_direccion_billing_fn=lambda billing_info: "Fiscal 123",
        ml_extraer_telefono_fn=lambda order, shipment: "2991234567",
        ml_buyer_tiene_nombre_real_fn=lambda order: False,
        parece_nickname_ml_fn=lambda valor, nickname: valor == nickname,
        ml_datos_apb_pedido_fn=lambda pedido: ["datos de entrega"],
        generar_mensaje_contacto_ml_fn=lambda pedido: "Necesitamos datos de entrega",
    )

    assert resultado is pedido
    assert pedido.ml_buyer_id == "BUYER1"
    assert pedido.ml_buyer_nickname == "comprador_123"
    assert pedido.ml_nombre_real is True
    assert pedido.ml_datos_fiscales_ok is True
    assert pedido.ml_billing_nombre == "Juan Fiscal"
    assert pedido.ml_billing_documento == "20123456789"
    assert pedido.ml_billing_direccion == "Fiscal 123"
    assert pedido.cliente == "Juan Perez"
    assert pedido.dni == "20123456789"
    assert pedido.telefono == "2991234567"
    assert pedido.ml_campos_faltantes == "datos de entrega"
    assert pedido.ml_mensaje_contacto == "Necesitamos datos de entrega"


def test_ml_aplicar_apb_en_pedido_service_usa_billing_si_cliente_es_nickname():
    pedido = _pedido_ml_apb_fake()
    pedido.cliente = "comprador_123"

    _ml_aplicar_apb_en_pedido_service(
        pedido,
        order={"buyer": {"id": "BUYER1", "nickname": "comprador_123"}},
        shipment={},
        billing_info={},
        ml_nombre_cliente_fn=lambda order, shipment: "comprador_123",
        ml_extraer_nombre_billing_fn=lambda billing_info: "Maria Gomez",
        ml_extraer_documento_billing_fn=lambda billing_info: "",
        ml_extraer_direccion_billing_fn=lambda billing_info: "",
        ml_extraer_telefono_fn=lambda order, shipment: "",
        ml_buyer_tiene_nombre_real_fn=lambda order: False,
        parece_nickname_ml_fn=lambda valor, nickname: valor == nickname,
        ml_datos_apb_pedido_fn=lambda pedido: [],
        generar_mensaje_contacto_ml_fn=lambda pedido: "no deberia usarse",
    )

    assert pedido.cliente == "Maria Gomez"
    assert pedido.ml_mensaje_contacto == ""
    assert pedido.ml_campos_faltantes == ""


from services.ml_importacion import (
    ml_pedido_existente_operativo_service as _ml_pedido_existente_operativo_service,
    ml_pedido_existente_por_order_id_service as _ml_pedido_existente_por_order_id_service,
)


class _FakeId:
    @staticmethod
    def asc():
        return "id_asc"


class _FakeQuery:
    def __init__(self, pedidos):
        self.pedidos = pedidos

    def filter_by(self, **kwargs):
        filtrados = []
        for pedido in self.pedidos:
            if all(getattr(pedido, clave, None) == valor for clave, valor in kwargs.items()):
                filtrados.append(pedido)
        return _FakeQuery(filtrados)

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.pedidos[0] if self.pedidos else None


class _PedidoFake:
    id = _FakeId()
    query = _FakeQuery([])


def _configurar_pedidos_fake(pedidos):
    _PedidoFake.query = _FakeQuery(pedidos)


def test_ml_pedido_existente_por_order_id_service_prioriza_canal_ml():
    pedido_ml = _SimpleNamespace(
        canal="Mercado Libre",
        id_venta="ORDER1",
    )
    pedido_otro = _SimpleNamespace(
        canal="Tienda Nube",
        id_venta="ORDER1",
    )
    _configurar_pedidos_fake([pedido_ml, pedido_otro])

    resultado = _ml_pedido_existente_por_order_id_service(
        "ORDER1",
        _PedidoFake,
    )

    assert resultado is pedido_ml


def test_ml_pedido_existente_por_order_id_service_hace_fallback_por_id_venta():
    pedido_otro = _SimpleNamespace(
        canal="Tienda Nube",
        id_venta="ORDER1",
    )
    _configurar_pedidos_fake([pedido_otro])

    resultado = _ml_pedido_existente_por_order_id_service(
        "ORDER1",
        _PedidoFake,
    )

    assert resultado is pedido_otro


def test_ml_pedido_existente_operativo_service_mercado_envios_busca_por_pack():
    pedido_pack = _SimpleNamespace(
        canal="Mercado Libre",
        ml_pack_id="PACK1",
        ml_shipping_id="SHIP1",
        id_venta="ORDER_ANTERIOR",
    )
    _configurar_pedidos_fake([pedido_pack])

    resultado = _ml_pedido_existente_operativo_service(
        {"id": "ORDER1", "pack_id": "PACK1", "shipping": {"id": "SHIP1"}},
        {},
        _PedidoFake,
        ml_es_mercado_envios_order_fn=lambda order, shipment: True,
        ml_pedido_existente_por_order_id_fn=lambda order_id: None,
    )

    assert resultado is pedido_pack


def test_ml_pedido_existente_operativo_service_mercado_envios_busca_por_shipping_si_no_hay_pack():
    pedido_shipping = _SimpleNamespace(
        canal="Mercado Libre",
        ml_pack_id="",
        ml_shipping_id="SHIP1",
        id_venta="ORDER_ANTERIOR",
    )
    _configurar_pedidos_fake([pedido_shipping])

    resultado = _ml_pedido_existente_operativo_service(
        {"id": "ORDER1", "shipping": {"id": "SHIP1"}},
        {},
        _PedidoFake,
        ml_es_mercado_envios_order_fn=lambda order, shipment: True,
        ml_pedido_existente_por_order_id_fn=lambda order_id: None,
    )

    assert resultado is pedido_shipping


def test_ml_pedido_existente_operativo_service_acordas_usa_order_id():
    _configurar_pedidos_fake([])

    resultado = _ml_pedido_existente_operativo_service(
        {"id": "ORDER1", "shipping": {"id": "SHIP1"}},
        {},
        _PedidoFake,
        ml_es_mercado_envios_order_fn=lambda order, shipment: False,
        ml_pedido_existente_por_order_id_fn=lambda order_id: f"pedido:{order_id}",
    )

    assert resultado == "pedido:ORDER1"

