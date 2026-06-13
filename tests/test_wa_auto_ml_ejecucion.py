from services.wa_auto_ml_ejecucion import ejecutar_flujo_wa_desde_ml


class PedidoDummy:
    def __init__(self, pedido_id=123):
        self.id = pedido_id


def test_ejecutar_flujo_wa_desde_ml_con_faltantes_inicia_recoleccion_y_no_cross_sell():
    pedido = PedidoDummy(1)
    llamados = []

    resultado = ejecutar_flujo_wa_desde_ml(
        pedido=pedido,
        faltantes_limpios=["dni"],
        decision_flujo_wa={
            "accion": "Inició WhatsApp desde ML",
            "detalle_extra": "handoff ML→WA con ML cortado | dni",
        },
        wa_iniciar_desde_ml_fn=lambda p: llamados.append(("iniciar", p.id)) or True,
        wa_cerrar_datos_completos_fn=lambda p: llamados.append("cerrar") or True,
        cross_sell_post_datos_completos_fn=lambda **kwargs: llamados.append("cross"),
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("intentar_cross"),
        construir_log_error_cross_sell_fn=lambda error: f"error {error}",
    )

    assert resultado == {
        "ok": True,
        "accion": "Inició WhatsApp desde ML",
        "detalle_extra": "handoff ML→WA con ML cortado | dni",
    }
    assert llamados == [("iniciar", 1)]


def test_ejecutar_flujo_wa_desde_ml_sin_faltantes_cierra_datos_y_dispara_cross_sell():
    pedido = PedidoDummy(2)
    llamados = []

    resultado = ejecutar_flujo_wa_desde_ml(
        pedido=pedido,
        faltantes_limpios=[],
        decision_flujo_wa={
            "accion": "Inició WhatsApp con datos completos",
            "detalle_extra": "datos completos | cross-sell evaluado post handoff ML",
        },
        wa_iniciar_desde_ml_fn=lambda p: llamados.append("iniciar") or True,
        wa_cerrar_datos_completos_fn=lambda p: llamados.append(("cerrar", p.id)) or True,
        cross_sell_post_datos_completos_fn=lambda **kwargs: llamados.append(
            ("cross", kwargs["pedido"].id, kwargs["ok"])
        ),
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("intentar_cross"),
        construir_log_error_cross_sell_fn=lambda error: f"error {error}",
    )

    assert resultado == {
        "ok": True,
        "accion": "Inició WhatsApp con datos completos",
        "detalle_extra": "datos completos | cross-sell evaluado post handoff ML",
    }
    assert llamados == [
        ("cerrar", 2),
        ("cross", 2, True),
    ]


def test_ejecutar_flujo_wa_desde_ml_sin_faltantes_si_cerrar_falla_dispara_cross_sell_con_ok_false():
    pedido = PedidoDummy(3)
    llamados = []

    resultado = ejecutar_flujo_wa_desde_ml(
        pedido=pedido,
        faltantes_limpios=[],
        decision_flujo_wa={
            "accion": "Inició WhatsApp con datos completos",
            "detalle_extra": "datos completos | cross-sell evaluado post handoff ML",
        },
        wa_iniciar_desde_ml_fn=lambda p: llamados.append("iniciar") or True,
        wa_cerrar_datos_completos_fn=lambda p: llamados.append(("cerrar", p.id)) or False,
        cross_sell_post_datos_completos_fn=lambda **kwargs: llamados.append(
            ("cross", kwargs["pedido"].id, kwargs["ok"])
        ),
        intentar_cross_sell_fn=lambda *args, **kwargs: llamados.append("intentar_cross"),
        construir_log_error_cross_sell_fn=lambda error: f"error {error}",
    )

    assert resultado["ok"] is False
    assert llamados == [
        ("cerrar", 3),
        ("cross", 3, False),
    ]
