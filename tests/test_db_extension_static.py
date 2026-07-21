from pathlib import Path


def test_db_se_crea_fuera_de_app():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )
    extension = Path("extensions.py").read_text(
        encoding="utf-8-sig"
    )

    assert "from extensions import db" in app
    assert "db.init_app(app)" in app
    assert "db = SQLAlchemy(app)" not in app

    assert "db = SQLAlchemy()" in extension
    assert "from app import" not in extension


def test_modelos_de_app_conservan_misma_extension():
    app = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    assert "class Pedido(db.Model):" in app
    assert app.index("db.init_app(app)") < app.index(
        "class Pedido(db.Model):"
    )
