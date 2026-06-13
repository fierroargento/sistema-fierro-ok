from services.wa_auto_ml_transicion import intentar_avisar_transicion_ml_wa


class PedidoDummy:
    def __init__(self, pedido_id=123):
        self.id = pedido_id


def test_intentar_avisar_transicion_no_hace_nada_si_no_debe_avisar():
    pedido = PedidoDummy()
    llamados = []

    resumen = intentar_avisar_transicion_ml_wa(
        pedido=pedido,
        resumen_actual="resumen inicial",
        debe_avisar_fn=lambda p: False,
        texto_transicion_fn=lambda: llamados.append("texto"),
        puede_enviar_mensaje_fn=lambda **kwargs: llamados.append("puede_enviar"),
        enviar_mensaje_ml_fn=lambda *args: llamados.append("enviar"),
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append("registrar"),
        marcar_transicion_resumen_fn=lambda p: "resumen marcado",
        construir_log_bloqueado_fn=lambda pedido_id, motivo: "bloqueado",
        construir_log_error_fn=lambda pedido_id, error: "error",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resumen == "resumen inicial"
    assert llamados == []


def test_intentar_avisar_transicion_si_canal_manager_bloquea_loguea_y_no_envia():
    pedido = PedidoDummy(456)
    llamados = []

    resumen = intentar_avisar_transicion_ml_wa(
        pedido=pedido,
        resumen_actual="resumen inicial",
        debe_avisar_fn=lambda p: True,
        texto_transicion_fn=lambda: "texto ML",
        puede_enviar_mensaje_fn=lambda **kwargs: (False, "ownership bloqueado"),
        enviar_mensaje_ml_fn=lambda *args: llamados.append("enviar"),
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append("registrar"),
        marcar_transicion_resumen_fn=lambda p: "resumen marcado",
        construir_log_bloqueado_fn=lambda pedido_id, motivo: f"bloqueado {pedido_id} {motivo}",
        construir_log_error_fn=lambda pedido_id, error: "error",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resumen == "resumen inicial"
    assert llamados == ["bloqueado 456 ownership bloqueado"]


def test_intentar_avisar_transicion_envia_registra_y_devuelve_resumen_marcado():
    pedido = PedidoDummy(789)
    llamados = []

    resumen = intentar_avisar_transicion_ml_wa(
        pedido=pedido,
        resumen_actual="resumen inicial",
        debe_avisar_fn=lambda p: True,
        texto_transicion_fn=lambda: "texto ML",
        puede_enviar_mensaje_fn=lambda **kwargs: (True, ""),
        enviar_mensaje_ml_fn=lambda pedido, texto: llamados.append(("enviar", pedido.id, texto)),
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append(("registrar", kwargs["canal"], kwargs["texto"])),
        marcar_transicion_resumen_fn=lambda p: "resumen marcado",
        construir_log_bloqueado_fn=lambda pedido_id, motivo: "bloqueado",
        construir_log_error_fn=lambda pedido_id, error: "error",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resumen == "resumen marcado"
    assert llamados == [
        ("enviar", 789, "texto ML"),
        ("registrar", "ml", "texto ML"),
    ]


def test_intentar_avisar_transicion_si_falla_loguea_error_y_conserva_resumen():
    pedido = PedidoDummy(321)
    llamados = []

    def enviar_con_error(pedido, texto):
        raise RuntimeError("fallo envio")

    resumen = intentar_avisar_transicion_ml_wa(
        pedido=pedido,
        resumen_actual="resumen inicial",
        debe_avisar_fn=lambda p: True,
        texto_transicion_fn=lambda: "texto ML",
        puede_enviar_mensaje_fn=lambda **kwargs: (True, ""),
        enviar_mensaje_ml_fn=enviar_con_error,
        registrar_envio_automatico_fn=lambda **kwargs: llamados.append("registrar"),
        marcar_transicion_resumen_fn=lambda p: "resumen marcado",
        construir_log_bloqueado_fn=lambda pedido_id, motivo: "bloqueado",
        construir_log_error_fn=lambda pedido_id, error: f"error {pedido_id} {error}",
        print_fn=lambda texto: llamados.append(texto),
    )

    assert resumen == "resumen inicial"
    assert llamados == ["error 321 fallo envio"]
