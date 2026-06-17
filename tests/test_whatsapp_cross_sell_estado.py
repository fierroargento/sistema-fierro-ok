import modules.whatsapp.flows as flows
import services.cross_sell_rules as cross_sell_rules


class PedidoDummy:
    def __init__(self):
        self.id = 123
        self.telefono = "+5492920123456"
        self.empresa_envio = "Via Cargo"
        self.tipo_entrega = "Sucursal"
        self.sucursal_nombre = "Viedma"
        self.ia_requiere_operador = True
        self.wa_estado = ""


def _patch_base(monkeypatch, eventos, estados_conversacionales, estados_wa):
    monkeypatch.setattr(
        cross_sell_rules,
        "puede_iniciar_cross_sell_pedido",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        flows,
        "normalizar_telefono_service",
        lambda telefono: "5492920123456",
    )
    monkeypatch.setattr(
        flows,
        "obtener_productos_a_ofrecer",
        lambda pedido: ["KIT_PALA"],
    )
    monkeypatch.setattr(
        flows,
        "actualizar_estado_conversacional_wa",
        lambda *args, **kwargs: estados_conversacionales.append((args, kwargs)),
    )
    monkeypatch.setattr(
        flows,
        "_guardar_estado_wa",
        lambda *args, **kwargs: estados_wa.append((args, kwargs)),
    )
    monkeypatch.setattr(
        flows,
        "registrar_evento_operativo_wa",
        lambda **kwargs: eventos.append(kwargs),
    )


def test_wa_iniciar_cross_sell_no_marca_estado_si_todos_los_envios_fallan(monkeypatch):
    pedido = PedidoDummy()
    eventos = []
    estados_conversacionales = []
    estados_wa = []

    _patch_base(monkeypatch, eventos, estados_conversacionales, estados_wa)

    monkeypatch.setattr(
        flows,
        "wa_enviar_texto",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        flows,
        "wa_ofrecer_producto",
        lambda *args, **kwargs: False,
    )

    resultado = flows.wa_iniciar_cross_sell(
        pedido,
        origen="bot",
        forzar=True,
    )

    assert resultado is False
    assert estados_conversacionales == []
    assert estados_wa == []
    assert eventos
    assert eventos[0]["resultado"] == "error"
    assert eventos[0]["estado_conversacional"] == ""


def test_wa_iniciar_cross_sell_marca_estado_solo_si_algun_envio_sale(monkeypatch):
    pedido = PedidoDummy()
    eventos = []
    estados_conversacionales = []
    estados_wa = []

    _patch_base(monkeypatch, eventos, estados_conversacionales, estados_wa)

    monkeypatch.setattr(
        flows,
        "wa_enviar_texto",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        flows,
        "wa_ofrecer_producto",
        lambda *args, **kwargs: True,
    )

    resultado = flows.wa_iniciar_cross_sell(
        pedido,
        origen="bot",
        forzar=True,
    )

    assert resultado is True
    assert len(estados_conversacionales) == 1
    assert estados_conversacionales[0][1]["estado_conversacional"] == "cross_sell"
    assert estados_conversacionales[0][1]["cross_sell_activo"] is True
    assert len(estados_wa) == 1
    assert estados_wa[0][0][1] == "cross_sell:KIT_PALA:0"
    assert eventos
    assert eventos[0]["resultado"] == "ok"
    assert eventos[0]["estado_conversacional"] == "cross_sell"
