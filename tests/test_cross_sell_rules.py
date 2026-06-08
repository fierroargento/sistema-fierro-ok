from domain.estados import Estado
from services.cross_sell_rules import (
    cross_sell_ya_gestionado,
    debe_bloquear_etiqueta_lista_por_cross_sell,
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
        estado=Estado.CARGANDO,
        empresa_envio="Vía Cargo",
        tipo_entrega="Sucursal",
        sucursal_nombre="",
        codigo_postal="3000",
        items=None,
        ia_faltantes="",
        ia_campos_faltantes="",
        ml_campos_faltantes="",
        ia_recolector_estado="",
        ia_requiere_operador=False,
        wa_estado="",
    ):
        self.id = 1
        self.canal = canal
        self.ml_tipo = ml_tipo
        self.estado = estado
        self.empresa_envio = empresa_envio
        self.tipo_entrega = tipo_entrega
        self.sucursal_nombre = sucursal_nombre
        self.codigo_postal = codigo_postal
        self.items = items if items is not None else [
            ItemFake(sku="PF8050H", descripcion="Parrilla 80x50")
        ]
        self.ia_faltantes = ia_faltantes
        self.ia_campos_faltantes = ia_campos_faltantes
        self.ml_campos_faltantes = ml_campos_faltantes
        self.ia_recolector_estado = ia_recolector_estado
        self.ia_requiere_operador = ia_requiere_operador
        self.wa_estado = wa_estado


def test_permite_cross_sell_auto_con_datos_completos_aunque_falte_sucursal():
    pedido = PedidoFake(sucursal_nombre="")

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


def test_permite_cross_sell_pp6040_con_cp_aunque_transporte_no_este_cerrado():
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
    ) == ""


def test_bloquea_cross_sell_si_faltan_datos_del_recolector():
    pedido = PedidoFake(ia_faltantes='["dni"]')

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "datos_incompletos"


def test_bloquea_cross_sell_si_no_hay_productos_configurados():
    pedido = PedidoFake(
        items=[ItemFake(sku="SIN-CROSS", descripcion="Producto sin cross-sell")]
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "sin_productos_cross_sell"


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


def test_bloquea_cross_sell_auto_en_etiqueta_lista():
    pedido = PedidoFake(estado=Estado.ETIQUETA_LISTA)

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "pedido_en_etapa_posterior"


def test_permite_cross_sell_manual_en_preparacion_antes_de_despachado():
    pedido = PedidoFake(estado=Estado.ETIQUETA_LISTA)

    assert puede_iniciar_cross_sell_pedido(
        pedido,
        modo="operador",
        manual_enabled=True,
    ) is True


def test_bloquea_cross_sell_en_estado_despachado():
    pedido = PedidoFake(estado=Estado.DESPACHADO)

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "pedido_en_etapa_posterior"

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        manual_enabled=True,
    ) == "pedido_en_etapa_posterior"


def test_bloquea_etiqueta_lista_si_cross_sell_no_fue_gestionado():
    pedido = PedidoFake(estado=Estado.CARGANDO)

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is True


def test_no_bloquea_etiqueta_lista_si_cross_sell_ya_fue_iniciado():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        wa_estado="cross_sell:KITPACH:0",
    )

    assert cross_sell_ya_gestionado(pedido) is True

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is False


def test_no_bloquea_etiqueta_lista_si_no_hay_productos_configurados():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        items=[ItemFake(sku="SIN-CROSS", descripcion="Producto sin cross-sell")],
    )

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is False


def test_no_bloquea_etiqueta_lista_si_cross_sell_deshabilitado_total():
    pedido = PedidoFake(estado=Estado.CARGANDO)

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=False,
        manual_enabled=False,
    ) is False

def test_no_bloquea_cross_sell_si_solo_falta_sucursal_logistica():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        ml_campos_faltantes="sucursal",
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        manual_enabled=True,
    ) == ""


def test_no_bloquea_cross_sell_si_faltante_logistico_esta_en_json():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        ia_faltantes='["sucursal", "transporte"]',
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == ""


def test_bloquea_cross_sell_si_falta_dni_comercial():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        ia_faltantes='["dni"]',
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="auto",
        auto_enabled=True,
    ) == "datos_incompletos"



def test_no_bloquea_cross_sell_si_falta_datos_de_entrega_logistica():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        ml_campos_faltantes="datos de entrega",
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        manual_enabled=True,
    ) == ""


def test_no_bloquea_cross_sell_si_falta_tipo_de_entrega_logistica():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        ml_campos_faltantes="tipo de entrega",
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        manual_enabled=True,
    ) == ""


def test_no_bloquea_cross_sell_si_falta_ubicacion_logistica():
    pedido = PedidoFake(
        estado=Estado.CARGANDO,
        ia_faltantes='["provincia", "localidad", "código postal", "dirección"]',
    )

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        manual_enabled=True,
    ) == ""        