from services.cross_sell_rules import (
    motivo_bloqueo_cross_sell,
    puede_iniciar_cross_sell_pedido,
)


class ItemFake:
    def __init__(self, sku="", descripcion=""):
        self.sku = sku
        self.descripcion = descripcion


class PedidoFake:
    def __init__(
        self,
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
        estado="Cargando Pedido",
        empresa_envio="Vía Cargo",
        tipo_entrega="Sucursal",
        sucursal_nombre="Agencia Santa Fe",
        codigo_postal="3000",
        items=None,
        ia_campos_faltantes="",
        ia_recolector_estado="",
        ia_requiere_operador=False,
    ):
        self.canal = canal
        self.ml_tipo = ml_tipo
        self.estado = estado
        self.empresa_envio = empresa_envio
        self.tipo_entrega = tipo_entrega
        self.sucursal_nombre = sucursal_nombre
        self.codigo_postal = codigo_postal
        self.items = items if items is not None else [
            ItemFake(sku="PF8050J", descripcion="Parrilla 80x50")
        ]
        self.ia_campos_faltantes = ia_campos_faltantes
        self.ia_recolector_estado = ia_recolector_estado
        self.ia_requiere_operador = ia_requiere_operador


def test_permite_cross_sell_ml_acordas_via_cargo_con_sucursal():
    pedido = PedidoFake()

    assert puede_iniciar_cross_sell_pedido(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) is True

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == ""


def test_bloquea_cross_sell_ml_acordas_via_cargo_sin_sucursal():
    pedido = PedidoFake(sucursal_nombre="")

    assert puede_iniciar_cross_sell_pedido(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) is False

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "logistica_abierta"


def test_bloquea_cross_sell_pp6040_sin_transporte():
    pedido = PedidoFake(
        empresa_envio="",
        tipo_entrega="",
        sucursal_nombre="",
        items=[ItemFake(sku="PP6040H", descripcion="Parrilla plegable")],
        codigo_postal="8504",
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "logistica_abierta"


def test_permite_cross_sell_pp6040_con_cp_y_transporte():
    pedido = PedidoFake(
        empresa_envio="Correo Argentino",
        tipo_entrega="Sucursal",
        sucursal_nombre="",
        items=[ItemFake(sku="PP6040H", descripcion="Parrilla plegable")],
        codigo_postal="8504",
    )

    assert puede_iniciar_cross_sell_pedido(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) is True


def test_bloquea_cross_sell_si_auto_deshabilitado():
    pedido = PedidoFake()

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=False,
    ) == "cross_sell_auto_deshabilitado"


def test_bloquea_cross_sell_manual_si_manual_deshabilitado_y_no_forzado():
    pedido = PedidoFake()

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        manual_enabled=False,
        forzar=False,
    ) == "cross_sell_manual_deshabilitado"


def test_permite_cross_sell_manual_forzado_aunque_manual_este_deshabilitado():
    pedido = PedidoFake()

    assert puede_iniciar_cross_sell_pedido(
        pedido,
        modo="operador",
        manual_enabled=False,
        forzar=True,
    ) is True


def test_bloquea_cross_sell_en_estado_despachado():
    pedido = PedidoFake(estado="Despachado")

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "pedido_en_etapa_posterior"