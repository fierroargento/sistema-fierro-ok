from services.logistica_defaults import aplicar_default_via_cargo_sucursal_ml_acordas
from tests.fixtures.pedido_factory import ItemFake, PedidoFake


def test_ml_acordas_no_pp6040_aplica_via_cargo_sucursal_por_defecto():
    pedido = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="",
        tipo_entrega="",
        items=[ItemFake(sku="PF8050J", descripcion="Parrilla De Hierro 80x50")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is True
    assert pedido.empresa_envio == "Vía Cargo"
    assert pedido.tipo_entrega == "Sucursal"


def test_ml_acordas_pp6040_no_fuerza_via_cargo():
    pedido = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="",
        tipo_entrega="",
        items=[ItemFake(sku="PP6040H", descripcion="Parrilla plegable")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is False
    assert pedido.empresa_envio == ""
    assert pedido.tipo_entrega == ""


def test_no_pisa_transporte_o_tipo_ya_definidos():
    pedido = PedidoFake(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        empresa_envio="Andreani",
        tipo_entrega="Domicilio",
        items=[ItemFake(sku="PF8050J", descripcion="Parrilla De Hierro 80x50")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is False
    assert pedido.empresa_envio == "Andreani"
    assert pedido.tipo_entrega == "Domicilio"


def test_no_aplica_fuera_de_ml_acordas():
    pedido = PedidoFake(
        canal="Tienda Nube",
        ml_tipo="",
        empresa_envio="",
        tipo_entrega="",
        items=[ItemFake(sku="PF8050J", descripcion="Parrilla De Hierro 80x50")],
    )

    modificado = aplicar_default_via_cargo_sucursal_ml_acordas(pedido)

    assert modificado is False
    assert pedido.empresa_envio == ""
    assert pedido.tipo_entrega == ""