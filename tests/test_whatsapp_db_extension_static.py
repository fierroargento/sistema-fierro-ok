from pathlib import Path


def test_flows_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert "from app import db" not in texto


def test_flows_conserva_operaciones_transaccionales():
    texto = Path(
        "modules/whatsapp/flows.py"
    ).read_text(encoding="utf-8-sig")

    assert "db.session.commit()" in texto
    assert "db.session.rollback()" in texto


def test_flows_postventa_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/flows_postventa.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert "from app import db" not in texto


def test_flows_postventa_conserva_transacciones():
    texto = Path(
        "modules/whatsapp/flows_postventa.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "db.session.commit()"
    ) == 2
    assert texto.count(
        "db.session.rollback()"
    ) == 2
