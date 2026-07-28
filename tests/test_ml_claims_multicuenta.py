from pathlib import Path
from types import SimpleNamespace

from services.ml_claims import (
    ml_sync_claims_pedidos_operativos_service,
)


class CampoFake:
    def __eq__(self, _otro):
        return self

    def in_(self, _valores):
        return self


class QueryPedidosFake:
    def __init__(self, pedidos):
        self.pedidos = list(pedidos)

    def filter(self, *_condiciones):
        return self

    def all(self):
        return list(self.pedidos)


class SessionFake:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_sync_claims_consulta_cada_pedido_con_su_contexto():
    pedido_1 = SimpleNamespace(
        id=1,
        id_venta="order-111",
        ml_pack_id="pack-111",
        ml_seller_id="111",
    )
    pedido_2 = SimpleNamespace(
        id=2,
        id_venta="order-222",
        ml_pack_id="pack-222",
        ml_seller_id="222",
    )

    class PedidoFake:
        canal = CampoFake()
        estado = CampoFake()
        query = QueryPedidosFake([
            pedido_1,
            pedido_2,
        ])

    session = SessionFake()
    db = SimpleNamespace(session=session)
    consultas = []
    marcaciones = []

    def obtener_claim(pedido, order_id, pack_id):
        consultas.append(
            (
                pedido.id,
                pedido.ml_seller_id,
                order_id,
                pack_id,
            )
        )
        if pedido is pedido_2:
            return {"id": "claim-222"}
        return None

    resultado = ml_sync_claims_pedidos_operativos_service(
        PedidoFake,
        db,
        obtener_claim,
        lambda pedido, claim: marcaciones.append(
            (pedido.id, claim)
        ),
        ["Cargando Pedido"],
    )

    assert consultas == [
        (1, "111", "order-111", "pack-111"),
        (2, "222", "order-222", "pack-222"),
    ]
    assert marcaciones == [
        (1, None),
        (2, {"id": "claim-222"}),
    ]
    assert resultado == 1
    assert session.commits == 1
    assert session.rollbacks == 0


def test_app_conecta_claims_con_cuenta_del_pedido():
    app = Path("app.py").read_text(encoding="utf-8-sig")

    inicio_adaptador = app.index(
        "def ml_obtener_claim_de_pedido("
    )
    fin_adaptador = app.index(
        "\ndef ml_sync_claims_pedidos_operativos():",
        inicio_adaptador,
    )
    adaptador = app[inicio_adaptador:fin_adaptador]

    inicio_sync = fin_adaptador + 1
    fin_sync = app.index(
        "\ndef ml_pedido_tiene_claim(",
        inicio_sync,
    )
    sync = app[inicio_sync:fin_sync]

    assert "cuenta_por_pedido(" in adaptador
    assert "ml_api_contexto(" in adaptador
    assert "ml_api_get=api_context.get_json" in adaptador
    assert "ml_obtener_claim_de_pedido" in sync
    assert "cuenta_ml_actual" not in sync
