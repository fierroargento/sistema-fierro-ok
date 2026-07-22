"""
Modelo de auditoría de webhooks de Tienda Nube.
"""

from extensions import db
from services.fechas import ahora_utc_naive


class TiendaNubeWebhookLog(db.Model):
    """Registro persistido de una notificación de Tienda Nube."""

    __tablename__ = "tienda_nube_webhook_log"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(120))
    tn_order_id = db.Column(db.String(50))
    payload = db.Column(db.Text)
    fecha = db.Column(
        db.DateTime,
        default=ahora_utc_naive,
    )
    procesado = db.Column(
        db.Boolean,
        default=False,
    )
    error = db.Column(db.Text)
