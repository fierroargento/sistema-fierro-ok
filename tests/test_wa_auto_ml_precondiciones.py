from services.wa_auto_ml_precondiciones import evaluar_precondiciones_wa_auto_ml


class PedidoDummy:
    def __init__(self, telefono="2920123456", contacto_iniciado=True):
        self.telefono = telefono
        self.contacto_iniciado = contacto_iniciado


def test_evaluar_precondiciones_no_aplica_si_no_hay_pedido():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=None,
        flag_wa_auto_desde_ml="1",
        es_ml_acordas_entrega_fn=lambda pedido: True,
        puede_hacer_handoff_fn=lambda pedido: (True, ""),
        normalizar_telefono_fn=lambda tel: "5492920123456",
    )

    assert resultado == {
        "ok": False,
        "motivo": "no_aplica",
    }


def test_evaluar_precondiciones_no_aplica_si_no_es_ml_acordas():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=PedidoDummy(),
        flag_wa_auto_desde_ml="1",
        es_ml_acordas_entrega_fn=lambda pedido: False,
        puede_hacer_handoff_fn=lambda pedido: (True, ""),
        normalizar_telefono_fn=lambda tel: "5492920123456",
    )

    assert resultado == {
        "ok": False,
        "motivo": "no_aplica",
    }


def test_evaluar_precondiciones_respeta_flag_apagado():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=PedidoDummy(),
        flag_wa_auto_desde_ml="off",
        es_ml_acordas_entrega_fn=lambda pedido: True,
        puede_hacer_handoff_fn=lambda pedido: (True, ""),
        normalizar_telefono_fn=lambda tel: "5492920123456",
    )

    assert resultado == {
        "ok": False,
        "motivo": "apagado",
    }


def test_evaluar_precondiciones_frena_si_ml_no_iniciado():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=PedidoDummy(contacto_iniciado=False),
        flag_wa_auto_desde_ml="1",
        es_ml_acordas_entrega_fn=lambda pedido: True,
        puede_hacer_handoff_fn=lambda pedido: (True, ""),
        normalizar_telefono_fn=lambda tel: "5492920123456",
    )

    assert resultado == {
        "ok": False,
        "motivo": "ml_no_iniciado",
    }


def test_evaluar_precondiciones_frena_si_canal_manager_no_permiso():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=PedidoDummy(),
        flag_wa_auto_desde_ml="1",
        es_ml_acordas_entrega_fn=lambda pedido: True,
        puede_hacer_handoff_fn=lambda pedido: (False, "handoff_bloqueado"),
        normalizar_telefono_fn=lambda tel: "5492920123456",
    )

    assert resultado == {
        "ok": False,
        "motivo": "handoff_bloqueado",
    }


def test_evaluar_precondiciones_frena_si_telefono_invalido():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=PedidoDummy(),
        flag_wa_auto_desde_ml="1",
        es_ml_acordas_entrega_fn=lambda pedido: True,
        puede_hacer_handoff_fn=lambda pedido: (True, ""),
        normalizar_telefono_fn=lambda tel: "549115734719",
    )

    assert resultado == {
        "ok": False,
        "motivo": "sin_telefono_valido",
    }


def test_evaluar_precondiciones_ok_devuelve_tel_y_motivo_handoff():
    resultado = evaluar_precondiciones_wa_auto_ml(
        pedido=PedidoDummy(),
        flag_wa_auto_desde_ml="1",
        es_ml_acordas_entrega_fn=lambda pedido: True,
        puede_hacer_handoff_fn=lambda pedido: (True, "handoff_ok"),
        normalizar_telefono_fn=lambda tel: "5492920123456",
    )

    assert resultado == {
        "ok": True,
        "tel": "5492920123456",
        "motivo_handoff": "handoff_ok",
    }
