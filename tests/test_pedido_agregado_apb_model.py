from pathlib import Path

from models.pedido_agregado_apb import PedidoAgregadoAPB


def test_pedido_agregado_apb_expone_modelo_canonico():
    assert (
        PedidoAgregadoAPB.__tablename__
        == "pedido_agregado_apb"
    )

    columnas = {
        "id",
        "pedido_id",
        "usuario",
        "rol",
        "fecha",
        "comprobante_dux_url",
        "comprobante_dux_public_id",
        "comprobante_pago_url",
        "comprobante_pago_public_id",
        "items_json",
    }

    assert columnas.issubset(
        set(PedidoAgregadoAPB.__dict__)
    )


def test_pedido_agregado_apb_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/pedido_agregado_apb.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert 'db.ForeignKey("pedido.id")' in modelo
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class PedidoAgregadoAPB" not in app
    assert (
        "from models.pedido_agregado_apb import "
        "PedidoAgregadoAPB"
        in app
    )
