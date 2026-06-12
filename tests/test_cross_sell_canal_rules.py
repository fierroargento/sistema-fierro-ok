from domain.estados import Estado
from services.cross_sell_rules import (
    canal_es_elegible_para_cross_sell_obligatorio,
    debe_bloquear_etiqueta_lista_por_cross_sell,
    motivo_bloqueo_cross_sell,
)


class PedidoFake:
    def __init__(self, canal, ml_tipo=""):
        self.id = 1
        self.estado = Estado.CARGANDO
        self.canal = canal
        self.ml_tipo = ml_tipo
        self.wa_estado = ""
        self.ia_recolector_estado = ""
        self.ia_faltantes = ""
        self.ia_campos_faltantes = ""
        self.ml_campos_faltantes = ""


def test_tienda_nube_es_elegible_para_cross_sell_obligatorio():
    pedido = PedidoFake("Tienda Nube")

    assert canal_es_elegible_para_cross_sell_obligatorio(pedido) is True


def test_ml_acordas_es_elegible_para_cross_sell_obligatorio():
    pedido = PedidoFake("Mercado Libre", "Acordás la Entrega")

    assert canal_es_elegible_para_cross_sell_obligatorio(pedido) is True


def test_presencial_no_es_elegible_para_cross_sell_obligatorio():
    pedido = PedidoFake("Presencial")

    assert canal_es_elegible_para_cross_sell_obligatorio(pedido) is False


def test_mayorista_no_es_elegible_para_cross_sell_obligatorio():
    pedido = PedidoFake("Mayorista")

    assert canal_es_elegible_para_cross_sell_obligatorio(pedido) is False


def test_mercado_envios_no_es_elegible_para_cross_sell_obligatorio():
    pedido = PedidoFake("Mercado Libre", "Mercado Envíos")

    assert canal_es_elegible_para_cross_sell_obligatorio(pedido) is False


def test_presencial_no_bloquea_aunque_tenga_productos(monkeypatch):
    import modules.whatsapp.cross_sell as cross_sell

    monkeypatch.setattr(
        cross_sell,
        "obtener_productos_a_ofrecer",
        lambda pedido: ["TEST-UPSELL"],
    )

    pedido = PedidoFake("Presencial")

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is False

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        auto_enabled=True,
        manual_enabled=True,
    ) == "canal_no_obliga_cross_sell"


def test_mayorista_no_bloquea_aunque_tenga_productos(monkeypatch):
    import modules.whatsapp.cross_sell as cross_sell

    monkeypatch.setattr(
        cross_sell,
        "obtener_productos_a_ofrecer",
        lambda pedido: ["TEST-UPSELL"],
    )

    pedido = PedidoFake("Mayorista")

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is False

    assert motivo_bloqueo_cross_sell(
        pedido,
        modo="operador",
        auto_enabled=True,
        manual_enabled=True,
    ) == "canal_no_obliga_cross_sell"


def test_tienda_nube_bloquea_si_tiene_productos_y_no_gestiono_cross_sell(monkeypatch):
    import modules.whatsapp.cross_sell as cross_sell

    monkeypatch.setattr(
        cross_sell,
        "obtener_productos_a_ofrecer",
        lambda pedido: ["TEST-UPSELL"],
    )

    pedido = PedidoFake("Tienda Nube")

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is True


def test_ml_acordas_bloquea_si_tiene_productos_y_no_gestiono_cross_sell(monkeypatch):
    import modules.whatsapp.cross_sell as cross_sell

    monkeypatch.setattr(
        cross_sell,
        "obtener_productos_a_ofrecer",
        lambda pedido: ["TEST-UPSELL"],
    )

    pedido = PedidoFake("Mercado Libre", "Acordás la Entrega")

    assert debe_bloquear_etiqueta_lista_por_cross_sell(
        pedido,
        auto_enabled=True,
        manual_enabled=True,
    ) is True
