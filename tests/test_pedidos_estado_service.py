from services.pedidos_estado import (
    es_via_cargo,
    despacho_completo,
    requiere_contacto_cliente,
    siguiente_estado,
)
from tests.fixtures.pedido_factory import PedidoFake, pedido_ml_acordas, pedido_ml_mercado_envios


def test_es_via_cargo_variantes():
    assert es_via_cargo("Vía Cargo") is True
    assert es_via_cargo("Via Cargo") is True
    assert es_via_cargo("via cargo") is True
    assert es_via_cargo("Andreani") is False
    assert es_via_cargo("") is False


def test_despacho_completo_sucursal():
    p = pedido_ml_acordas()
    assert despacho_completo(p) is True


def test_despacho_completo_infiere_sucursal_si_tipo_vacio():
    p = pedido_ml_acordas(tipo_entrega="")
    assert despacho_completo(p) is True


def test_despacho_incompleto_sin_sucursal():
    p = pedido_ml_acordas()
    p.sucursal_nombre = ""
    assert despacho_completo(p) is False


def test_domicilio_completo():
    p = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="Correo Argentino",
        tipo_entrega="Domicilio",
        direccion="Av. Corrientes 1234",
        codigo_postal="1043",
        localidad="Buenos Aires",
        provincia="Buenos Aires",
    )
    assert despacho_completo(p) is True


def test_acordas_completo_no_requiere_contacto():
    p = pedido_ml_acordas()
    assert requiere_contacto_cliente(p) is False


def test_acordas_incompleto_requiere_contacto():
    p = pedido_ml_acordas()
    p.sucursal_nombre = ""
    assert requiere_contacto_cliente(p) is True


def test_mercado_envios_no_requiere_contacto():
    p = pedido_ml_mercado_envios()
    assert requiere_contacto_cliente(p) is False


def test_siguiente_estado_flujo_normal():
    assert siguiente_estado("Cargando Pedido") == "Etiqueta Lista"
    assert siguiente_estado("Etiqueta Lista") == "Etiqueta Impresa"
    assert siguiente_estado("Etiqueta Impresa") == "Embalado"
    assert siguiente_estado("Embalado") == "Despachado"
    assert siguiente_estado("Despachado") == "Entregado"


def test_siguiente_estado_terminal():
    assert siguiente_estado("Entregado") is None
    assert siguiente_estado("Finalizado") is None