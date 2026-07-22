from pathlib import Path

from models.pedido_ignorado_ml import PedidoIgnoradoML


def test_pedido_ignorado_ml_expone_modelo_canonico():
    assert (
        PedidoIgnoradoML.__tablename__
        == "pedido_ignorado_ml"
    )

    columnas = {
        "id",
        "id_venta",
        "motivo",
        "pedido_local_id",
        "usuario",
        "fecha",
    }

    assert columnas.issubset(
        set(PedidoIgnoradoML.__dict__)
    )


def test_pedido_ignorado_ml_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/pedido_ignorado_ml.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class PedidoIgnoradoML" not in app
    assert (
        "from models.pedido_ignorado_ml import "
        "PedidoIgnoradoML"
        in app
    )
