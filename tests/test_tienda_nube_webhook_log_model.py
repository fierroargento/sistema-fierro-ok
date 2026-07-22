from pathlib import Path

from models.tienda_nube_webhook_log import (
    TiendaNubeWebhookLog,
)


def test_tienda_nube_webhook_log_expone_modelo_canonico():
    assert (
        TiendaNubeWebhookLog.__tablename__
        == "tienda_nube_webhook_log"
    )

    columnas = {
        "id",
        "event",
        "tn_order_id",
        "payload",
        "fecha",
        "procesado",
        "error",
    }

    assert columnas.issubset(
        set(TiendaNubeWebhookLog.__dict__)
    )


def test_tienda_nube_webhook_log_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/tienda_nube_webhook_log.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class TiendaNubeWebhookLog" not in app
    assert (
        "from models.tienda_nube_webhook_log import "
        "TiendaNubeWebhookLog"
        in app
    )
