from services.wa_auto_ml_cross_sell import intentar_cross_sell_post_datos_completos


class PedidoDummy:
    def __init__(self, pedido_id=123):
        self.id = pedido_id


def test_intentar_cross_sell_post_datos_completos_no_hace_nada_si_ok_false():
    pedido = PedidoDummy()
    llamados = []

    resultado = intentar_cross_sell_post_datos_completos(
        pedido=pedido,
        ok=False,
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("cross"),
        construir_log_error_fn=lambda error: f"error {error}",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resultado is False
    assert llamados == []


def test_intentar_cross_sell_post_datos_completos_dispara_con_origen_correcto():
    pedido = PedidoDummy(456)
    llamados = []

    resultado = intentar_cross_sell_post_datos_completos(
        pedido=pedido,
        ok=True,
        intentar_cross_sell_fn=lambda pedido, origen_disparo: llamados.append(
            (pedido.id, origen_disparo)
        ),
        construir_log_error_fn=lambda error: f"error {error}",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resultado is True
    assert llamados == [(456, "ml_datos_completos")]


def test_intentar_cross_sell_post_datos_completos_si_falla_loguea_y_no_bloquea():
    pedido = PedidoDummy(789)
    llamados = []

    def cross_sell_con_error(pedido, origen_disparo):
        raise RuntimeError("fallo cross")

    resultado = intentar_cross_sell_post_datos_completos(
        pedido=pedido,
        ok=True,
        intentar_cross_sell_fn=cross_sell_con_error,
        construir_log_error_fn=lambda error: f"error {error}",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resultado is False
    assert llamados == ["error fallo cross"]
