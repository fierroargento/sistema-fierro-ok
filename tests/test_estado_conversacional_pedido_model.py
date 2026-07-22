from pathlib import Path

from models.estado_conversacional_pedido import (
    EstadoConversacionalPedido,
)


def test_estado_conversacional_expone_modelo_canonico():
    assert (
        EstadoConversacionalPedido.__tablename__
        == "estado_conversacional_pedido"
    )

    columnas = {
        "id",
        "pedido_id",
        "owner_actual",
        "estado_conversacional",
        "canal_activo",
        "flujo_base",
        "takeover_activo",
        "bot_pausado",
        "cross_sell_activo",
        "ultima_interaccion",
        "ultimo_mensaje_cliente",
        "ultimo_mensaje_bot",
        "fecha_creacion",
        "fecha_actualizacion",
    }

    assert columnas.issubset(
        set(EstadoConversacionalPedido.__dict__)
    )


def test_estado_conversacional_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/estado_conversacional_pedido.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert 'db.ForeignKey("pedido.id")' in modelo
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class EstadoConversacionalPedido" not in app
    assert (
        "from models.estado_conversacional_pedido import "
        "EstadoConversacionalPedido"
        in app
    )
