from services.bandejas_inicio import (
    BANDEJA_DEMORA,
    BANDEJA_PENDIENTES_CARGA,
    BANDEJA_PENDIENTES_DESPACHO,
    BANDEJA_SEGUIMIENTO,
    atributos_filtro_pedido,
    clasificar_bandeja_pedido,
    pedido_en_seguimiento,
    pedido_pendiente_carga,
    pedido_pendiente_despacho,
    requiere_cargar_seguimiento_via_cargo,
    resumen_operativo_bandejas,
)


class PedidoFake:
    def __init__(
        self,
        estado="Cargando Pedido",
        empresa_envio="",
        seguimiento="",
        tn_tracking_number="",
    ):
        self.estado = estado
        self.empresa_envio = empresa_envio
        self.seguimiento = seguimiento
        self.tn_tracking_number = tn_tracking_number


def test_cargando_pedido_es_pendiente_carga():
    pedido = PedidoFake(estado="Cargando Pedido")

    assert pedido_pendiente_carga(pedido) is True
    assert clasificar_bandeja_pedido(pedido) == BANDEJA_PENDIENTES_CARGA


def test_via_cargo_despachado_sin_seguimiento_es_pendiente_carga():
    pedido = PedidoFake(
        estado="Despachado",
        empresa_envio="Vía Cargo",
        seguimiento="",
    )

    assert requiere_cargar_seguimiento_via_cargo(pedido) is True
    assert pedido_pendiente_carga(pedido) is True
    assert pedido_en_seguimiento(pedido) is False
    assert clasificar_bandeja_pedido(pedido) == BANDEJA_PENDIENTES_CARGA


def test_via_cargo_despachado_con_seguimiento_es_seguimiento():
    pedido = PedidoFake(
        estado="Despachado",
        empresa_envio="Vía Cargo",
        seguimiento="VC123",
    )

    assert requiere_cargar_seguimiento_via_cargo(pedido) is False
    assert pedido_pendiente_carga(pedido) is False
    assert pedido_en_seguimiento(pedido) is True
    assert clasificar_bandeja_pedido(pedido) == BANDEJA_SEGUIMIENTO


def test_etiqueta_lista_es_pendiente_despacho():
    pedido = PedidoFake(estado="Etiqueta Lista")

    assert pedido_pendiente_despacho(pedido) is True
    assert clasificar_bandeja_pedido(pedido) == BANDEJA_PENDIENTES_DESPACHO


def test_etiqueta_impresa_es_pendiente_despacho():
    pedido = PedidoFake(estado="Etiqueta Impresa")

    assert pedido_pendiente_despacho(pedido) is True
    assert clasificar_bandeja_pedido(pedido) == BANDEJA_PENDIENTES_DESPACHO


def test_embalado_es_pendiente_despacho():
    pedido = PedidoFake(estado="Embalado")

    assert pedido_pendiente_despacho(pedido) is True
    assert clasificar_bandeja_pedido(pedido) == BANDEJA_PENDIENTES_DESPACHO


def test_agregado_pendiente_prioriza_carga_aunque_este_en_preparacion():
    pedido = PedidoFake(estado="Etiqueta Lista")

    assert pedido_pendiente_carga(
        pedido,
        agregado_pendiente_fn=lambda p: True,
    ) is True

    assert pedido_pendiente_despacho(
        pedido,
        agregado_pendiente_fn=lambda p: True,
    ) is False

    assert clasificar_bandeja_pedido(
        pedido,
        agregado_pendiente_fn=lambda p: True,
    ) == BANDEJA_PENDIENTES_CARGA


def test_con_demora_queda_en_bandeja_demora():
    pedido = PedidoFake(estado="Con demora de entrega")

    assert clasificar_bandeja_pedido(pedido) == BANDEJA_DEMORA


def test_resumen_operativo_bandejas_cuenta_por_responsabilidad():
    pedidos = [
        PedidoFake(estado="Cargando Pedido"),
        PedidoFake(estado="Etiqueta Lista"),
        PedidoFake(estado="Despachado", empresa_envio="Vía Cargo", seguimiento=""),
        PedidoFake(estado="Despachado", empresa_envio="Vía Cargo", seguimiento="VC123"),
        PedidoFake(estado="Con demora de entrega"),
    ]

    resumen = resumen_operativo_bandejas(pedidos)

    assert resumen == {
        BANDEJA_PENDIENTES_CARGA: 2,
        BANDEJA_PENDIENTES_DESPACHO: 1,
        BANDEJA_SEGUIMIENTO: 1,
        BANDEJA_DEMORA: 1,
        "total": 5,
    }


def test_atributos_filtro_pedido_devuelve_flags_para_template():
    pedido = PedidoFake(
        estado="Despachado",
        empresa_envio="Vía Cargo",
        seguimiento="",
    )

    assert atributos_filtro_pedido(pedido) == {
        BANDEJA_PENDIENTES_CARGA: "si",
        BANDEJA_PENDIENTES_DESPACHO: "no",
        BANDEJA_SEGUIMIENTO: "no",
        BANDEJA_DEMORA: "no",
    }

def test_normalizar_filtro_inicio_rechaza_valores_invalidos():
    from services.bandejas_inicio import BANDEJA_TODOS, normalizar_filtro_inicio

    assert normalizar_filtro_inicio("pendientes_carga") == "pendientes_carga"
    assert normalizar_filtro_inicio("valor_raro") == BANDEJA_TODOS
    assert normalizar_filtro_inicio("") == BANDEJA_TODOS
    assert normalizar_filtro_inicio(None) == BANDEJA_TODOS


def test_filtrar_pedidos_por_bandeja_devuelve_solo_la_bandeja_pedida():
    from services.bandejas_inicio import filtrar_pedidos_por_bandeja

    pendiente_carga = PedidoFake(estado="Cargando Pedido")
    pendiente_despacho = PedidoFake(estado="Etiqueta Lista")
    seguimiento = PedidoFake(
        estado="Despachado",
        empresa_envio="Vía Cargo",
        seguimiento="VC123",
    )

    pedidos = [pendiente_carga, pendiente_despacho, seguimiento]

    assert filtrar_pedidos_por_bandeja(
        pedidos,
        "pendientes_carga",
    ) == [pendiente_carga]

    assert filtrar_pedidos_por_bandeja(
        pedidos,
        "pendientes_despacho",
    ) == [pendiente_despacho]

    assert filtrar_pedidos_por_bandeja(
        pedidos,
        "seguimiento",
    ) == [seguimiento]


def test_preparar_bandejas_inicio_devuelve_resumen_total_y_pedidos_filtrados():
    from services.bandejas_inicio import preparar_bandejas_inicio

    pendiente_carga = PedidoFake(estado="Cargando Pedido")
    pendiente_despacho = PedidoFake(estado="Etiqueta Lista")
    seguimiento = PedidoFake(
        estado="Despachado",
        empresa_envio="Vía Cargo",
        seguimiento="VC123",
    )

    resumen, pedidos_filtrados, filtro = preparar_bandejas_inicio(
        [pendiente_carga, pendiente_despacho, seguimiento],
        "pendientes_carga",
    )

    assert filtro == "pendientes_carga"
    assert pedidos_filtrados == [pendiente_carga]
    assert resumen["pendientes_carga"] == 1
    assert resumen["pendientes_despacho"] == 1
    assert resumen["seguimiento"] == 1
    assert resumen["total"] == 3
