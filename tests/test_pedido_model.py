from pathlib import Path

from models.pedido import Pedido


def test_pedido_expone_modelo_canonico():
    assert Pedido.__tablename__ == "pedido"

    campos_criticos = {
        "id",
        "cliente",
        "dni",
        "telefono",
        "mail",
        "canal",
        "id_venta",
        "estado",
        "origen",
        "ml_cuenta_id",
        "ml_seller_id",
        "ml_pack_id",
        "ml_shipping_id",
        "tn_order_id",
        "ia_recolector_estado",
        "ia_requiere_operador",
        "wa_estado",
        "wa_paso_operativo",
        "empresa_envio",
        "tipo_entrega",
        "direccion",
        "codigo_postal",
        "localidad",
        "provincia",
        "seguimiento",
        "tracking_ultima_sync",
        "fecha_creacion",
        "fecha_despachado",
        "fecha_entregado",
        "items",
    }

    assert campos_criticos <= set(Pedido.__dict__)


def test_pedido_conserva_fk_multicuenta_y_relacion_items():
    modelo = Path(
        "models/pedido.py"
    ).read_text(encoding="utf-8")

    assert (
        'db.ForeignKey("mercado_libre_cuenta.id")'
        in modelo
    )
    assert (
        'items = db.relationship('
        '"PedidoItem", cascade="all, delete-orphan"'
        ')'
        in modelo
    )


def test_pedido_no_depende_de_app():
    modelo = Path(
        "models/pedido.py"
    ).read_text(encoding="utf-8")
    app = Path(
        "app.py"
    ).read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert "from app import" not in modelo
    assert '__tablename__ = "pedido"' in modelo
    assert "default=ahora_utc_naive" in modelo
    assert "datetime.utcnow" not in modelo

    assert "class Pedido(db.Model):" not in app
    assert "from models.pedido import Pedido" in app
