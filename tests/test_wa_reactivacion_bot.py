from services.wa_reactivacion_bot import decidir_reactivacion_bot_wa


class PedidoFake:
    def __init__(self, wa_estado=""):
        self.wa_estado = wa_estado


def test_reactivar_bot_vuelve_a_cross_sell_si_estaba_en_cross_sell():
    decision = decidir_reactivacion_bot_wa(PedidoFake("cross_sell"))

    assert decision["wa_estado"] == "cross_sell"
    assert decision["estado_conversacional"] == "cross_sell"
    assert decision["motivo"] == "reactivar_cross_sell"


def test_reactivar_bot_vuelve_a_cross_sell_cerrado():
    decision = decidir_reactivacion_bot_wa(PedidoFake("cross_sell_cerrado"))

    assert decision["wa_estado"] == "cross_sell_cerrado"
    assert decision["estado_conversacional"] == "cross_sell_cerrado"


def test_reactivar_bot_vuelve_a_datos_completos_si_estaba_en_despacho():
    decision = decidir_reactivacion_bot_wa(PedidoFake("despacho_en_proceso"))

    assert decision["wa_estado"] == "despacho_en_proceso"
    assert decision["estado_conversacional"] == "datos_completos"


def test_reactivar_bot_vuelve_a_datos_completos_si_faltaba_transporte():
    decision = decidir_reactivacion_bot_wa(PedidoFake("falta_elegir_transporte"))

    assert decision["wa_estado"] == "falta_elegir_transporte"
    assert decision["estado_conversacional"] == "datos_completos"


def test_reactivar_bot_respeta_estado_operativo_post_despacho():
    decision = decidir_reactivacion_bot_wa(PedidoFake("despachado"))

    assert decision["wa_estado"] == "despachado"
    assert decision["estado_conversacional"] == "despachado"


def test_reactivar_bot_default_recolectando_datos_si_no_hay_estado():
    decision = decidir_reactivacion_bot_wa(PedidoFake(""))

    assert decision["wa_estado"] == "esperando_datos"
    assert decision["estado_conversacional"] == "recolectando_datos"
    assert decision["motivo"] == "reactivar_recoleccion"


def test_reactivar_bot_default_recolectando_datos_si_estaba_operador_manual():
    decision = decidir_reactivacion_bot_wa(PedidoFake("operador_manual"))

    assert decision["wa_estado"] == "esperando_datos"
    assert decision["estado_conversacional"] == "recolectando_datos"