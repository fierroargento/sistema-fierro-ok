import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from modules.whatsapp import post_despacho


class QueryFake:
    def __init__(self, resultado):
        self.resultado = resultado
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        return self

    def first(self):
        return self.resultado


class TrackingEventoFake:
    query = QueryFake(None)

    def __init__(self, **campos):
        for nombre, valor in campos.items():
            setattr(self, nombre, valor)


class SessionFake:
    def __init__(self):
        self.agregados = []
        self.rollbacks = 0

    def add(self, objeto):
        self.agregados.append(objeto)

    def rollback(self):
        self.rollbacks += 1


def instalar_dependencias(
    monkeypatch,
    *,
    evento_existente=None,
):
    consulta = QueryFake(evento_existente)
    TrackingEventoFake.query = consulta

    app_fake = ModuleType("app")
    app_fake.TrackingEvento = TrackingEventoFake
    monkeypatch.setitem(sys.modules, "app", app_fake)

    session = SessionFake()
    monkeypatch.setattr(
        post_despacho,
        "db",
        SimpleNamespace(session=session),
    )
    return consulta, session


def test_registrar_tracking_evento_agrega_evento_nuevo(
    monkeypatch,
):
    consulta, session = instalar_dependencias(monkeypatch)
    pedido = SimpleNamespace(id=123)

    resultado = post_despacho.registrar_tracking_evento(
        pedido,
        "Correo Argentino",
        "AB123",
        "Disponible en sucursal",
        "sucursal",
        raw_json={"estado": "sucursal"},
        origen="scheduler",
    )

    assert resultado is True
    assert consulta.filtros == {
        "pedido_id": 123,
        "empresa": "Correo Argentino",
        "seguimiento": "AB123",
        "estado": "Disponible en sucursal",
    }
    assert len(session.agregados) == 1

    evento = session.agregados[0]
    assert evento.pedido_id == 123
    assert evento.empresa == "Correo Argentino"
    assert evento.seguimiento == "AB123"
    assert evento.estado == "Disponible en sucursal"
    assert evento.clasificacion == "sucursal"
    assert evento.raw_json == {"estado": "sucursal"}
    assert evento.origen == "scheduler"
    assert evento.fecha_evento is not None


def test_registrar_tracking_evento_no_duplica(
    monkeypatch,
):
    existente = object()
    consulta, session = instalar_dependencias(
        monkeypatch,
        evento_existente=existente,
    )
    pedido = SimpleNamespace(id=456)

    resultado = post_despacho.registrar_tracking_evento(
        pedido,
        "Via Cargo",
        "XYZ789",
        "En sucursal",
        "sucursal",
    )

    assert resultado is False
    assert consulta.filtros["pedido_id"] == 456
    assert session.agregados == []


def test_error_del_workflow_hace_rollback(
    monkeypatch,
):
    session = SessionFake()
    monkeypatch.setattr(
        post_despacho,
        "db",
        SimpleNamespace(session=session),
    )

    def fallar_toma_operador(_pedido):
        raise RuntimeError("fallo controlado")

    monkeypatch.setattr(
        post_despacho,
        "wa_operador_tiene_toma_activa",
        fallar_toma_operador,
    )

    pedido = SimpleNamespace(
        canal="Mercado Libre",
        ml_tipo="Acordás la Entrega",
    )

    acciones = (
        post_despacho.procesar_evento_tracking_pedido(
            pedido,
            "sucursal",
            "En sucursal",
            origen="scheduler",
        )
    )

    assert acciones == []
    assert session.rollbacks == 1


def test_post_despacho_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/post_despacho.py"
    ).read_text(encoding="utf-8")

    assert texto.count("from extensions import db") == 1
    assert "from app import db" not in texto
    assert texto.count(
        "from app import TrackingEvento"
    ) == 1
    assert texto.count("db.session.add(ev)") == 1
    assert texto.count("db.session.rollback()") == 1
