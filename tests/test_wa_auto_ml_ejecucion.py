from services.wa_auto_ml_ejecucion import ejecutar_flujo_wa_desde_ml


class PedidoDummy:
    def __init__(self, pedido_id=123):
        self.id = pedido_id


def test_ejecutar_flujo_wa_desde_ml_con_faltantes_solo_inicia_wa_y_no_cross_sell():
    pedido = PedidoDummy(1)
    llamados = []

    resultado = ejecutar_flujo_wa_desde_ml(
        pedido=pedido,
        faltantes_limpios=["dni"],
        decision_flujo_wa={
            "accion": "Inicio WhatsApp desde ML",
            "detalle_extra": "handoff ML->WA con ML cortado | dni",
        },
        wa_iniciar_desde_ml_fn=lambda p: llamados.append(("iniciar", p.id)) or True,
        wa_cerrar_datos_completos_fn=lambda p: llamados.append("cerrar") or True,
        cross_sell_post_datos_completos_fn=lambda **kwargs: llamados.append("cross"),
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("intentar_cross"),
        construir_log_error_cross_sell_fn=lambda error: f"error {error}",
    )

    assert resultado == {
        "ok": True,
        "accion": "Inicio WhatsApp desde ML",
        "detalle_extra": "handoff ML->WA con ML cortado | dni",
        "espera_respuesta_cliente_wa": True,
    }
    assert llamados == [("iniciar", 1)]


def test_ejecutar_flujo_wa_desde_ml_sin_faltantes_tambien_espera_respuesta_cliente():
    pedido = PedidoDummy(2)
    llamados = []

    resultado = ejecutar_flujo_wa_desde_ml(
        pedido=pedido,
        faltantes_limpios=[],
        decision_flujo_wa={
            "accion": "Inicio WhatsApp con datos completos",
            "detalle_extra": "datos completos | espera respuesta cliente WA",
        },
        wa_iniciar_desde_ml_fn=lambda p: llamados.append(("iniciar", p.id)) or True,
        wa_cerrar_datos_completos_fn=lambda p: llamados.append(("cerrar", p.id)) or True,
        cross_sell_post_datos_completos_fn=lambda **kwargs: llamados.append("cross"),
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("intentar_cross"),
        construir_log_error_cross_sell_fn=lambda error: f"error {error}",
    )

    assert resultado == {
        "ok": True,
        "accion": "Inicio WhatsApp con datos completos",
        "detalle_extra": "datos completos | espera respuesta cliente WA",
        "espera_respuesta_cliente_wa": True,
    }
    assert llamados == [("iniciar", 2)]


def test_ejecutar_flujo_wa_desde_ml_si_apertura_falla_no_encadena_mensajes():
    pedido = PedidoDummy(3)
    llamados = []

    resultado = ejecutar_flujo_wa_desde_ml(
        pedido=pedido,
        faltantes_limpios=[],
        decision_flujo_wa={
            "accion": "Inicio WhatsApp desde ML",
            "detalle_extra": "ventana cerrada",
        },
        wa_iniciar_desde_ml_fn=lambda p: llamados.append(("iniciar", p.id)) or False,
        wa_cerrar_datos_completos_fn=lambda p: llamados.append("cerrar") or True,
        cross_sell_post_datos_completos_fn=lambda **kwargs: llamados.append("cross"),
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("intentar_cross"),
        construir_log_error_cross_sell_fn=lambda error: f"error {error}",
    )

    assert resultado == {
        "ok": False,
        "accion": "Inicio WhatsApp desde ML",
        "detalle_extra": "ventana cerrada",
        "espera_respuesta_cliente_wa": True,
    }
    assert llamados == [("iniciar", 3)]
