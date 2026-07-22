from pathlib import Path

from models.tracking_evento import TrackingEvento


def test_modelo_tracking_conserva_contrato():
    assert TrackingEvento.__tablename__ == (
        "tracking_evento"
    )

    for nombre in (
        "id",
        "pedido_id",
        "empresa",
        "seguimiento",
        "estado",
        "clasificacion",
        "raw_json",
        "origen",
        "fecha_evento",
    ):
        assert hasattr(TrackingEvento, nombre)

    fuente = Path(
        "models/tracking_evento.py"
    ).read_text(encoding="utf-8-sig")

    assert "class TrackingEvento(db.Model):" in fuente
    assert '__tablename__ = "tracking_evento"' in fuente
    assert 'db.ForeignKey("pedido.id")' in fuente
    assert "nullable=False" in fuente
    assert fuente.count(
        "default=ahora_utc_naive"
    ) == 1


def test_app_importa_modelo_tracking_canonico():
    fuente = Path("app.py").read_text(
        encoding="utf-8-sig"
    )

    assert (
        "from models.tracking_evento import "
        "TrackingEvento"
        in fuente
    )
    assert "class TrackingEvento(db.Model):" not in fuente
