from pathlib import Path

from models.nota_pedido import NotaPedido


def test_nota_pedido_expone_modelo_canonico():
    assert NotaPedido.__tablename__ == "nota_pedido"

    columnas = {
        "id",
        "pedido_id",
        "texto",
        "usuario",
        "rol",
        "fecha",
    }

    assert columnas.issubset(set(NotaPedido.__dict__))


def test_nota_pedido_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/nota_pedido.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert 'db.ForeignKey("pedido.id")' in modelo
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class NotaPedido" not in app
    assert "from models.nota_pedido import NotaPedido" in app
