import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from modules.whatsapp import webhook


class QueryFake:
    def __init__(self, resultado):
        self.resultado = resultado
        self.filtros = None

    def filter_by(self, **filtros):
        self.filtros = filtros
        return self

    def first(self):
        return self.resultado


class WhatsAppMensajeFake:
    query = QueryFake(None)


class SessionFake:
    def __init__(self, fallar_commit=False):
        self.fallar_commit = fallar_commit
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1
        if self.fallar_commit:
            raise RuntimeError("fallo controlado")

    def rollback(self):
        self.rollbacks += 1


def instalar_app_mensaje(
    monkeypatch,
    mensaje,
):
    consulta = QueryFake(mensaje)
    WhatsAppMensajeFake.query = consulta

    app_fake = ModuleType("app")
    app_fake.WhatsAppMensaje = WhatsAppMensajeFake
    monkeypatch.setitem(sys.modules, "app", app_fake)

    return consulta


def instalar_db(
    monkeypatch,
    *,
    fallar_commit=False,
):
    session = SessionFake(
        fallar_commit=fallar_commit,
    )
    monkeypatch.setattr(
        webhook,
        "db",
        SimpleNamespace(session=session),
    )
    return session


def test_status_meta_actualiza_y_persiste(
    monkeypatch,
):
    mensaje = SimpleNamespace(
        estado="enviado",
        error="error anterior",
    )
    consulta = instalar_app_mensaje(
        monkeypatch,
        mensaje,
    )
    session = instalar_db(monkeypatch)

    webhook._procesar_statuses_whatsapp([
        {
            "id": "wamid.123",
            "status": "delivered",
        },
    ])

    assert consulta.filtros == {
        "message_id_meta": "wamid.123",
    }
    assert mensaje.estado == "entregado"
    assert mensaje.error == ""
    assert session.commits == 1
    assert session.rollbacks == 0


def test_status_meta_hace_rollback_si_falla_commit(
    monkeypatch,
):
    mensaje = SimpleNamespace(
        estado="pendiente",
        error="",
    )
    instalar_app_mensaje(monkeypatch, mensaje)
    session = instalar_db(
        monkeypatch,
        fallar_commit=True,
    )

    webhook._procesar_statuses_whatsapp([
        {
            "id": "wamid.456",
            "status": "read",
        },
    ])

    assert mensaje.estado == "leido"
    assert session.commits == 1
    assert session.rollbacks == 1


def test_operador_manual_persiste_pendiente(
    monkeypatch,
):
    session = instalar_db(monkeypatch)

    monkeypatch.setattr(
        webhook,
        "get_wa_paso_operativo",
        lambda _pedido: None,
    )

    pedido = SimpleNamespace(
        wa_estado="operador_manual",
        ml_mensajes_pendientes=False,
        ml_mensajes_pendientes_count=2,
        ia_requiere_operador=False,
    )

    resultado = webhook._routear_mensaje(
        pedido,
        "Hola",
        "5491112345678",
    )

    assert resultado is None
    assert pedido.ml_mensajes_pendientes is True
    assert pedido.ml_mensajes_pendientes_count == 3
    assert pedido.ia_requiere_operador is True
    assert session.commits == 1


def test_webhook_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/webhook.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count("from extensions import db") == 1
    assert "from app import db" not in texto

    assert texto.count(
        "from app import WhatsAppMensaje"
    ) == 2
    assert texto.count(
        "from models.whatsapp_media import "
        "WhatsAppMediaRecibida"
    ) == 1
    assert (
        "from app import WhatsAppMediaRecibida"
        not in texto
    )

    assert texto.count("db.session.commit()") == 3
    assert texto.count("db.session.rollback()") == 2
