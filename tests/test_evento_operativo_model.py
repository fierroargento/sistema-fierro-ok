from pathlib import Path
from types import SimpleNamespace

from models.evento_operativo import EventoOperativo
from modules.whatsapp import cross_sell_auto


class QueryFake:
    def __init__(self, resultado):
        self.resultado = resultado
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        return self

    def first(self):
        return self.resultado


class EventoOperativoFake:
    query = QueryFake(None)


def test_modelo_evento_operativo_conserva_contrato():
    assert EventoOperativo.__tablename__ == (
        "evento_operativo"
    )

    for nombre in (
        "id",
        "pedido_id",
        "tipo_evento",
        "origen",
        "canal",
        "owner",
        "estado_conversacional",
        "flujo_base",
        "payload_json",
        "resultado",
        "detalle",
        "usuario",
        "procesado",
        "fecha",
    ):
        assert hasattr(EventoOperativo, nombre)

    fuente = Path(
        "models/evento_operativo.py"
    ).read_text(encoding="utf-8-sig")

    assert "class EventoOperativo(db.Model):" in fuente
    assert '__tablename__ = "evento_operativo"' in fuente
    assert 'db.ForeignKey("pedido.id")' in fuente
    assert "nullable=True" in fuente
    assert "default=ahora_utc_naive" in fuente


def test_cross_sell_consulta_modelo_extraido(
    monkeypatch,
):
    consulta = QueryFake(object())
    EventoOperativoFake.query = consulta

    monkeypatch.setattr(
        cross_sell_auto,
        "EventoOperativo",
        EventoOperativoFake,
    )

    pedido = SimpleNamespace(id=321)

    assert (
        cross_sell_auto
        ._cross_sell_ya_iniciado_por_evento(pedido)
        is True
    )
    assert consulta.filtros == {
        "pedido_id": 321,
        "tipo_evento": "cross_sell_iniciado",
        "resultado": "ok",
    }


def test_cross_sell_sin_evento_devuelve_falso(
    monkeypatch,
):
    EventoOperativoFake.query = QueryFake(None)

    monkeypatch.setattr(
        cross_sell_auto,
        "EventoOperativo",
        EventoOperativoFake,
    )

    assert (
        cross_sell_auto
        ._cross_sell_ya_iniciado_por_evento(
            SimpleNamespace(id=654),
        )
        is False
    )


def test_consumidores_no_importan_evento_desde_app():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    cross = Path(
        "modules/whatsapp/cross_sell_auto.py"
    ).read_text(encoding="utf-8-sig")

    assert (
        "from models.evento_operativo import "
        "EventoOperativo"
        in app
    )
    assert (
        "from models.evento_operativo import "
        "EventoOperativo"
        in cross
    )
    assert "class EventoOperativo(db.Model):" not in app
    assert "from app import EventoOperativo" not in cross
