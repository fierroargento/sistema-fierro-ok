from types import SimpleNamespace

from modules.whatsapp.flows_transporte import pedido_requiere_sucursal_via_cargo_pendiente


def test_tienda_nube_via_cargo_sin_sucursal_requiere_sucursal():
    pedido = SimpleNamespace(
        canal="Tienda Nube",
        tipo_ml="",
        empresa_envio="Vía Cargo",
        tipo_entrega="Sucursal",
        sucursal_nombre="",
    )

    assert pedido_requiere_sucursal_via_cargo_pendiente(pedido) is True


def test_tienda_nube_via_cargo_requiere_sucursal_aunque_tipo_entrega_venga_vacio():
    pedido = SimpleNamespace(
        canal="Tienda Nube",
        tipo_ml="",
        empresa_envio="Via Cargo",
        tipo_entrega="",
        sucursal_nombre="",
    )

    assert pedido_requiere_sucursal_via_cargo_pendiente(pedido) is True


def test_tienda_nube_via_cargo_con_sucursal_no_requiere_sucursal():
    pedido = SimpleNamespace(
        canal="Tienda Nube",
        tipo_ml="",
        empresa_envio="Vía Cargo",
        tipo_entrega="Sucursal",
        sucursal_nombre="Vía Cargo Viedma",
    )

    assert pedido_requiere_sucursal_via_cargo_pendiente(pedido) is False


def test_mercado_libre_acordas_via_cargo_sigue_requiriendo_sucursal():
    pedido = SimpleNamespace(
        canal="Mercado Libre",
        tipo_ml="Acordás la entrega",
        empresa_envio="Via Cargo",
        tipo_entrega="Sucursal",
        sucursal_nombre="",
    )

    assert pedido_requiere_sucursal_via_cargo_pendiente(pedido) is True


def test_mercado_libre_no_acordas_no_requiere_sucursal():
    pedido = SimpleNamespace(
        canal="Mercado Libre",
        tipo_ml="Mercado Envíos",
        empresa_envio="Via Cargo",
        tipo_entrega="Sucursal",
        sucursal_nombre="",
    )

    assert pedido_requiere_sucursal_via_cargo_pendiente(pedido) is False


def test_tienda_nube_no_via_cargo_no_requiere_sucursal():
    pedido = SimpleNamespace(
        canal="Tienda Nube",
        tipo_ml="",
        empresa_envio="Andreani",
        tipo_entrega="Domicilio",
        sucursal_nombre="",
    )

    assert pedido_requiere_sucursal_via_cargo_pendiente(pedido) is False
