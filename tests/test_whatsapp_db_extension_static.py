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


def test_flows_transporte_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/flows_transporte.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert "from app import db" not in texto
    assert (
        "from app import aplicar_default_tipo_entrega"
        in texto
    )


def test_flows_transporte_conserva_transacciones():
    texto = Path(
        "modules/whatsapp/flows_transporte.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "db.session.commit()"
    ) == 4
    assert texto.count(
        "db.session.rollback()"
    ) == 6


def test_general_routes_usa_extension_canonica_db():
    texto = Path(
        "modules/whatsapp/general_routes.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "from extensions import db"
    ) == 1
    assert (
        "WhatsAppMensaje, db, rol_actual"
        not in texto
    )
    assert texto.count(
        "from app import Pedido, "
        "WhatsAppMensaje, rol_actual"
    ) == 4


def test_general_routes_conserva_transacciones():
    texto = Path(
        "modules/whatsapp/general_routes.py"
    ).read_text(encoding="utf-8-sig")

    assert texto.count(
        "db.session.commit()"
    ) == 2
    assert texto.count(
        "db.session.rollback()"
    ) == 2
