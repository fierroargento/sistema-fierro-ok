from pathlib import Path

from models.pedido_item import PedidoItem


def test_pedido_item_expone_modelo_canonico():
    assert PedidoItem.__tablename__ == "pedido_item"

    columnas = {
        "id",
        "pedido_id",
        "sku",
        "descripcion",
        "cantidad",
        "cantidad_devuelta_ok",
        "cantidad_devuelta_danada",
        "estado_devolucion_item",
        "observacion_devolucion_item",
    }

    assert columnas.issubset(set(PedidoItem.__dict__))


def test_pedido_item_no_depende_de_app():
    modelo = Path(
        "models/pedido_item.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert 'db.ForeignKey("pedido.id")' in modelo
    assert "class PedidoItem" not in app
    assert "from models.pedido_item import PedidoItem" in app
    assert (
        'db.relationship("PedidoItem", '
        'cascade="all, delete-orphan")'
        in app
    )
