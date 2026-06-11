from services import canal_manager


class PedidoFake:
    def __init__(self):
        self.empresa_envio = "Via Cargo"
        self.tipo_entrega = "Sucursal"
        self.sucursal_nombre = ""
        self.codigo_postal = "8370"
        self.ia_requiere_operador = False
        self.ia_recolector_estado = ""
        self.ia_faltantes = ""
        self.ml_tipo = "Acordás la Entrega"


def test_ml_acordas_via_cargo_sin_sucursal_no_bloquea_inicio_wa(monkeypatch):
    pedido = PedidoFake()

    monkeypatch.setattr(
        canal_manager,
        "ml_acordas_via_cargo_sin_sucursal",
        lambda _pedido: True,
    )

    monkeypatch.setattr(
        canal_manager,
        "ml_acordas_via_cargo_puede_pasar_a_wa_por_no_respuesta",
        lambda _pedido: False,
    )

    assert canal_manager.ml_acordas_via_cargo_bloquea_inicio_wa(pedido) is False


def test_logistica_abierta_sigue_bloqueando_cross_sell_si_falta_sucursal(monkeypatch):
    pedido = PedidoFake()

    monkeypatch.setattr(
        canal_manager,
        "pedido_es_ml_acordas_ownership",
        lambda _pedido: True,
    )

    monkeypatch.setattr(
        canal_manager,
        "pedido_es_plegable_pp6040_ownership",
        lambda _pedido: False,
    )

    monkeypatch.setattr(
        canal_manager,
        "_faltantes_recolector_pedido",
        lambda _pedido: [],
    )

    assert canal_manager.ml_acordas_logistica_abierta_bloquea_cross_sell(pedido) is True
