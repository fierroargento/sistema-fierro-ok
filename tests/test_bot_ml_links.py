from modules.bot_ml.links import (
    ml_link_chat_venta,
    ml_link_detalle_venta,
)


class PedidoFake:
    def __init__(self, canal="Mercado Libre", id_venta="", ml_pack_id=""):
        self.canal = canal
        self.id_venta = id_venta
        self.ml_pack_id = ml_pack_id


def test_ml_link_detalle_venta_vacio_si_no_es_ml():
    pedido = PedidoFake(canal="Tienda Nube", id_venta="123")

    assert ml_link_detalle_venta(pedido) == ""


def test_ml_link_detalle_venta_vacio_si_no_tiene_id_venta():
    pedido = PedidoFake(canal="Mercado Libre", id_venta="")

    assert ml_link_detalle_venta(pedido) == ""


def test_ml_link_detalle_venta_arma_url():
    pedido = PedidoFake(canal="Mercado Libre", id_venta="20000000001")

    assert ml_link_detalle_venta(pedido) == (
        "https://www.mercadolibre.com.ar/ventas/20000000001/detalle"
    )


def test_ml_link_chat_venta_vacio_si_no_es_ml():
    pedido = PedidoFake(canal="Presencial", id_venta="20000000001")

    assert ml_link_chat_venta(pedido) == ""


def test_ml_link_chat_venta_prefiere_pack_id():
    pedido = PedidoFake(
        canal="Mercado Libre",
        id_venta="20000000001",
        ml_pack_id="30000000002",
    )

    url = ml_link_chat_venta(pedido)

    assert "/mensajeria/30000000002" in url
    assert "source=ml" in url


def test_ml_link_chat_venta_usa_id_venta_como_fallback():
    pedido = PedidoFake(
        canal="Mercado Libre",
        id_venta="20000000001",
        ml_pack_id="",
    )

    url = ml_link_chat_venta(pedido)

    assert "/mensajeria/20000000001" in url
    assert "callbackWording=Ventas" in url