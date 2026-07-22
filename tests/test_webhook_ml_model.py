from pathlib import Path

from models.webhook_ml import WebhookML


def test_webhook_ml_expone_modelo_canonico():
    assert WebhookML.__tablename__ == "webhook_ml"

    columnas = {
        "id",
        "topic",
        "resource",
        "payload",
        "fecha",
        "ok",
        "detalle",
    }

    assert columnas.issubset(set(WebhookML.__dict__))


def test_webhook_ml_no_depende_de_app_ni_utcnow():
    modelo = Path(
        "models/webhook_ml.py"
    ).read_text(encoding="utf-8")

    app = Path("app.py").read_text(encoding="utf-8")

    assert modelo.count("from extensions import db") == 1
    assert (
        "from services.fechas import ahora_utc_naive"
        in modelo
    )
    assert "datetime.utcnow" not in modelo
    assert "class WebhookML" not in app
    assert "from models.webhook_ml import WebhookML" in app
