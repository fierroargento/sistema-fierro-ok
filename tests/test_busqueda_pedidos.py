from pathlib import Path
from types import SimpleNamespace

from services import busqueda_pedidos


class CampoFake:
    def notin_(self, _valores):
        return self

    def desc(self):
        return self


class QueryFake:
    def __init__(self, resultados):
        self.resultados = resultados
        self.limite = None

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, limite):
        self.limite = limite
        return self

    def all(self):
        return self.resultados


class PedidoFake:
    estado = CampoFake()
    id = CampoFake()
    query = QueryFake([])


def test_wrapper_usa_modelo_pedido_canonico(monkeypatch):
    llamadas = []

    monkeypatch.setattr(
        busqueda_pedidos,
        "Pedido",
        PedidoFake,
    )
    monkeypatch.setattr(
        busqueda_pedidos,
        "buscar_pedido_activo_por_telefono_service",
        lambda telefono, modelo: llamadas.append(
            (telefono, modelo)
        ) or "pedido",
    )

    resultado = (
        busqueda_pedidos.buscar_pedido_activo_por_telefono(
            "2920123456"
        )
    )

    assert resultado == "pedido"
    assert llamadas == [("2920123456", PedidoFake)]


def test_service_encuentra_pedido_por_ultimos_ocho_digitos():
    esperado = SimpleNamespace(
        telefono="+54 9 2920 123456",
    )
    otro = SimpleNamespace(
        telefono="+54 9 291 5555555",
    )

    PedidoFake.query = QueryFake([otro, esperado])

    resultado = (
        busqueda_pedidos
        .buscar_pedido_activo_por_telefono_service(
            "02920-123456",
            PedidoFake,
        )
    )

    assert resultado is esperado
    assert PedidoFake.query.limite == 80


def test_modulos_whatsapp_no_importan_busqueda_desde_app():
    sender = Path(
        "modules/whatsapp/sender.py"
    ).read_text(encoding="utf-8-sig")
    webhook = Path(
        "modules/whatsapp/webhook.py"
    ).read_text(encoding="utf-8-sig")

    import_canonico = (
        "from services.busqueda_pedidos import "
        "buscar_pedido_activo_por_telefono"
    )

    assert import_canonico in sender
    assert import_canonico in webhook

    assert (
        "from app import buscar_pedido_activo_por_telefono"
        not in sender
    )
    assert (
        "from app import buscar_pedido_activo_por_telefono"
        not in webhook
    )
