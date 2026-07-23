from pathlib import Path
from types import SimpleNamespace

from modules.whatsapp import scheduler


class SessionFake:
    def __init__(self):
        self.rollbacks = 0
        self.removes = 0

    def rollback(self):
        self.rollbacks += 1

    def remove(self):
        self.removes += 1


def test_cierre_seguro_hace_rollback_y_remove(
    monkeypatch,
):
    session = SessionFake()

    monkeypatch.setattr(
        scheduler,
        "db",
        SimpleNamespace(session=session),
    )

    scheduler._cerrar_sesion_db_segura(
        rollback=True
    )

    assert session.rollbacks == 1
    assert session.removes == 1


def test_cierre_seguro_sin_error_solo_hace_remove(
    monkeypatch,
):
    session = SessionFake()

    monkeypatch.setattr(
        scheduler,
        "db",
        SimpleNamespace(session=session),
    )

    scheduler._cerrar_sesion_db_segura(
        rollback=False
    )

    assert session.rollbacks == 0
    assert session.removes == 1


def test_scheduler_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/scheduler.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert "from app import db" not in texto
    assert "Pedido, db" not in texto
    assert "db, Pedido" not in texto
    assert texto.count(
        "from models.pedido import Pedido"
    ) == 1
    assert "from app import Pedido" not in texto
    assert "\n            Pedido,\n" not in texto

    assert texto.count(
        "db.session.commit()"
    ) == 7
    assert texto.count(
        "db.session.rollback()"
    ) == 3
    assert texto.count(
        "db.session.remove()"
    ) == 1
