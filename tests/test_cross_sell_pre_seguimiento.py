from types import SimpleNamespace

from services.ml_sucursal_cross_sell_guard import intentar_wa_cross_sell_antes_de_seguimiento


def test_pre_seguimiento_no_frena_si_no_hay_cross_sell_pendiente():
    pedido = SimpleNamespace(ia_resumen="", ml_mensajes_pendientes=False, ia_requiere_operador=False)
    llamadas = {"wa": 0}

    def regla_no_bloquea(pedido, auto_enabled, manual_enabled, evento_operativo_model):
        return False

    def wa_fn(pedido, faltantes, motivo):
        llamadas["wa"] += 1
        return True, "wa_iniciado"

    resultado = intentar_wa_cross_sell_antes_de_seguimiento(
        pedido,
        cross_sell_rule_fn=regla_no_bloquea,
        wa_auto_iniciar_desde_ml_fn=wa_fn,
    )

    assert resultado["debe_frenar_seguimiento"] is False
    assert llamadas["wa"] == 0


def test_pre_seguimiento_frena_si_intenta_cross_sell():
    pedido = SimpleNamespace(ia_resumen="", ml_mensajes_pendientes=False, ia_requiere_operador=False)
    llamadas = {"wa": 0}

    def regla_bloquea(pedido, auto_enabled, manual_enabled, evento_operativo_model):
        return True

    def wa_fn(pedido, faltantes, motivo):
        llamadas["wa"] += 1
        assert faltantes == []
        assert motivo == "seguimiento_cargado_pre_despacho"
        return True, "wa_iniciado"

    resultado = intentar_wa_cross_sell_antes_de_seguimiento(
        pedido,
        cross_sell_rule_fn=regla_bloquea,
        wa_auto_iniciar_desde_ml_fn=wa_fn,
        motivo="seguimiento_cargado_pre_despacho",
    )

    assert resultado["ok"] is True
    assert resultado["debe_frenar_seguimiento"] is True
    assert llamadas["wa"] == 1


def test_pre_seguimiento_frena_y_marca_pendiente_si_wa_no_inicia():
    pedido = SimpleNamespace(ia_resumen="", ml_mensajes_pendientes=False, ia_requiere_operador=False)

    def regla_bloquea(pedido, auto_enabled, manual_enabled, evento_operativo_model):
        return True

    def wa_fn(pedido, faltantes, motivo):
        return False, "telefono_faltante"

    resultado = intentar_wa_cross_sell_antes_de_seguimiento(
        pedido,
        cross_sell_rule_fn=regla_bloquea,
        wa_auto_iniciar_desde_ml_fn=wa_fn,
    )

    assert resultado["ok"] is False
    assert resultado["debe_frenar_seguimiento"] is True
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ia_requiere_operador is True
