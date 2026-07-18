from modules.transportes import selector


class PedidoFake:
    def __init__(self):
        self.ia_requiere_operador = False
        self.ml_mensajes_pendientes = False
        self.wa_estado = ""
        self.ia_resumen = ""
        self.empresa_envio = ""
        self.tipo_entrega = ""


def test_sugerir_sucursales_correo_no_ensucia_si_flag_apagado(monkeypatch):
    pedido = PedidoFake()

    monkeypatch.setattr(selector, "correo_pp6040_habilitado", lambda: False)

    def explotar(_pedido):
        raise AssertionError("No debería buscar sucursales si Correo está deshabilitado")

    monkeypatch.setattr(selector, "obtener_sucursales_correo_por_pedido", explotar)

    resultado = selector.preparar_oferta_sucursales_correo_pedido(pedido)

    assert resultado.estado == "sin_oferta"
    assert pedido.ia_requiere_operador is False
    assert pedido.ml_mensajes_pendientes is False
    assert pedido.wa_estado == ""
    assert "TRANSPORTE" not in pedido.ia_resumen


def test_asignar_transporte_pedido_devuelve_mensaje_controlado_si_flag_apagado(monkeypatch):
    pedido = PedidoFake()

    monkeypatch.setattr(selector, "correo_pp6040_habilitado", lambda: False)

    ok, mensaje = selector.asignar_transporte_pedido(pedido)

    assert ok is False
    assert mensaje == "Cotización Correo temporalmente deshabilitada"
    assert pedido.empresa_envio == ""
