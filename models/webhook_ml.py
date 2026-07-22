"""
Modelo de auditoría de webhooks de Mercado Libre.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class WebhookML(db.Model):
    """Registro persistido de una notificación de Mercado Libre."""

    __tablename__ = "webhook_ml"

    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(80))
    resource = db.Column(db.String(300))
    payload = db.Column(db.Text)
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    ok = db.Column(
        db.Boolean,
        default=False,
    )
    detalle = db.Column(db.Text)
